"""Celery task wrapper around app.pipeline.map_pass.run_map_pass — one task PER CHUNK,
deliberately, not one task per document (Phase 4 gate: "chunk failures retry per-chunk,
not per-document"). Thin, per CLAUDE.md style; the actual map-pass logic lives in the
pipeline layer so it's testable without a broker.

Runs on the "llm" queue with an explicit time limit (docs/DECISIONS.md #47) — real
measured per-chunk latency ranges ~6s-135s (9 real chunks across 2 real documents),
comfortably inside the 600s/660s ceiling even with app.llm.client's own internal
retry/fallback.
"""

import uuid

from app.core.logging import get_logger
from app.storage.db import SessionLocal
from app.workers.celery_app import LLM_TASK_SOFT_TIME_LIMIT, LLM_TASK_TIME_LIMIT, celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="run_map_pass_for_chunk",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="llm",
    soft_time_limit=LLM_TASK_SOFT_TIME_LIMIT,
    time_limit=LLM_TASK_TIME_LIMIT,
)
def map_pass_chunk_task(self, chunk_id: str) -> str | None:
    """Returns the created ChunkExtraction's ID as a string, or None if this chunk
    permanently failed after exhausting retries. A failure here (a ProviderError from
    app.llm.client after both cloud and local fallback are exhausted) retries only
    this one chunk's task — every other chunk's task in the same document's fan-out is
    unaffected.

    Deliberately returns None on final failure instead of letting the exception
    propagate (docs/DECISIONS.md #62): this task is the header of a Celery chord
    (tasks_pipeline.py's map/reduce fan-out), and a chord's callback never fires if
    any header task ends in a failed state — a real bug found in practice, where one
    permanently-failed chunk out of 27 left an otherwise 96%-complete document stuck
    at "analyzing" forever. The reduce pass reads facts from `chunk_extractions`
    directly, not from this task's return value, so one missing chunk just means
    slightly less-complete source material, not a broken pipeline.
    """
    from app.models.chunk import Chunk
    from app.pipeline.map_pass import run_map_pass

    db = SessionLocal()
    try:
        chunk = db.get(Chunk, uuid.UUID(chunk_id))
        if chunk is None:
            raise ValueError(f"Chunk {chunk_id} not found")
        extraction = run_map_pass(db, chunk)
        return str(extraction.id)
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.error("map_pass.chunk_permanently_failed", chunk_id=chunk_id, error=str(exc))
        return None
    finally:
        db.close()
