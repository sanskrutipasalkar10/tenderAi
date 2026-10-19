"""Celery task wrapper around app.pipeline.chunk.build_chunks — thin, per CLAUDE.md
style; the actual chunk-planning logic lives in the pipeline layer so it's testable
without a broker.

A plain `chain(...)` link (like tasks_ingest.py, unlike map/reduce's chord headers,
docs/DECISIONS.md #62) — on exhausted retries this must explicitly mark the document
failed (app.workers._failure), or a dead chunk-planning step silently strands the
document at status="extracted" forever with no signal anywhere.
"""

import uuid

from app.core.logging import get_logger
from app.storage.db import SessionLocal
from app.workers._failure import mark_document_failed
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="build_chunks_for_document", bind=True, max_retries=3, default_retry_delay=30)
def build_chunks_task(self, document_id: str) -> list[str]:
    """Returns the created chunk IDs as strings, so a caller (tasks_pipeline.py, once
    it exists) can fan out one map-pass task per chunk (see tasks_map.py) — chunking
    itself is one task per document (it's cheap, no LLM call), but the map pass that
    follows is one task per chunk, so a single chunk's failure retries only that chunk.
    """
    from app.models.document import Document
    from app.pipeline.chunk import build_chunks

    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        chunks = build_chunks(db, document)
        return [str(chunk.id) for chunk in chunks]
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.error("chunk.permanently_failed", document_id=document_id, error=str(exc))
        mark_document_failed(
            document_id, f"Chunking failed after {self.max_retries} retries: {exc}"
        )
        raise
    finally:
        db.close()
