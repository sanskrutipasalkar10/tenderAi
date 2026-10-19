"""Shared "mark this document failed, visibly" helper — used by every task that sits
on the plain `chain(...)` portion of the pipeline (ingest -> chunk -> start_map_and_
reduce), where a Celery chain has no built-in equivalent of a chord's "callback always
fires" guarantee: if one chain link ends in a terminal failure, the next link simply
never runs, and nothing was writing `documents.status = "failed"` anywhere on that
path — a document could die mid-ingestion and sit at whatever status it last reached,
forever, with zero signal anywhere (the real, observed failure mode this module
closes). The three chord-based tasks (map_pass_chunk_task, the three reduce-module
tasks) don't need this: their chord callback always fires regardless of a header
task's outcome, so the pipeline still reaches a terminal status on its own.
"""

import uuid

from app.core.logging import get_logger
from app.storage.db import SessionLocal

logger = get_logger(__name__)


def mark_document_failed(document_id: str, reason: str) -> None:
    from app.models.document import Document

    logger.error("pipeline.document_failed", document_id=document_id, reason=reason)
    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is not None:
            document.status = "failed"
            document.failure_reason = reason
            db.commit()
    finally:
        db.close()
