"""Celery task wrapper around app.pipeline.map_pass.run_map_pass — one task PER CHUNK,
deliberately, not one task per document (Phase 4 gate: "chunk failures retry per-chunk,
not per-document"). Thin, per CLAUDE.md style; the actual map-pass logic lives in the
pipeline layer so it's testable without a broker.
"""

import uuid

from app.storage.db import SessionLocal
from app.workers.celery_app import celery_app


@celery_app.task(name="run_map_pass_for_chunk", bind=True, max_retries=3, default_retry_delay=30)
def map_pass_chunk_task(self, chunk_id: str) -> str:
    """Returns the created ChunkExtraction's ID as a string. A failure here (a
    ProviderError from app.llm.client after both cloud and local fallback are
    exhausted) retries only this one chunk's task — every other chunk's task in the
    same document's fan-out is unaffected.
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
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
