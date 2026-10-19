"""Celery task wrapper around app.services.ingestion — kept thin deliberately (CLAUDE.md
style: small, single-responsibility modules). The actual classify/extract/DB-write logic
lives in the service layer so it's testable without a broker.

Runs on the "llm" queue (docs/DECISIONS.md #47): scanned pages route through vision
extraction, a real Ollama call, so this task is LLM-bound like map/reduce, not cheap
like tasks_chunk.py. No per-task time limit here (see celery_app.py) — a whole
document's worth of pages can legitimately take longer than any single chunk/module
call.

Unlike map_pass_chunk_task/the reduce-module tasks (docs/DECISIONS.md #62), this task
is a plain `chain(...)` link, not a chord header — a chain has no built-in "the next
step always runs regardless" guarantee, so on exhausted retries this must explicitly
mark the document failed (app.workers._failure) before re-raising, or a genuinely dead
ingestion silently leaves the document stuck at whatever status it last reached,
forever, with zero signal anywhere — the real, observed failure mode this closes.
"""

import uuid

from app.core.logging import get_logger
from app.storage.db import SessionLocal
from app.workers._failure import mark_document_failed
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="ingest_document", bind=True, max_retries=3, default_retry_delay=30, queue="llm"
)
def ingest_document_task(self, document_id: str) -> None:
    from app.services import ingestion  # local import avoids a worker-boot circular import

    db = SessionLocal()
    try:
        ingestion.run_ingestion(db, uuid.UUID(document_id))
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.error("ingest.permanently_failed", document_id=document_id, error=str(exc))
        mark_document_failed(
            document_id, f"Ingestion failed after {self.max_retries} retries: {exc}"
        )
        raise
    finally:
        db.close()
