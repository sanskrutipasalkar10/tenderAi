"""Celery task wrapper around app.services.ingestion — kept thin deliberately (CLAUDE.md
style: small, single-responsibility modules). The actual classify/extract/DB-write logic
lives in the service layer so it's testable without a broker.

Runs on the "llm" queue (docs/DECISIONS.md #47): scanned pages route through vision
extraction, a real Ollama call, so this task is LLM-bound like map/reduce, not cheap
like tasks_chunk.py. No per-task time limit here (see celery_app.py) — a whole
document's worth of pages can legitimately take longer than any single chunk/module
call.
"""

import uuid

from app.storage.db import SessionLocal
from app.workers.celery_app import celery_app


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
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
