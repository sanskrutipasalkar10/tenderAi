"""Celery task wrapper around app.services.ingestion — kept thin deliberately (CLAUDE.md
style: small, single-responsibility modules). The actual classify/extract/DB-write logic
lives in the service layer so it's testable without a broker.
"""

import uuid

from app.storage.db import SessionLocal
from app.workers.celery_app import celery_app


@celery_app.task(name="ingest_document", bind=True, max_retries=3, default_retry_delay=30)
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
