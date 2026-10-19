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

Also holds `not_cancelled` — the user-initiated-stop cooperative-cancellation check
every pipeline task runs right after fetching its own Document, before doing any real
work. Celery here runs `--pool=solo` (one task at a time, synchronous, no separate
process per task), so there is no way to forcibly interrupt a task that's already
mid-flight — cancellation can only be cooperative: a task that hasn't started yet
checks the document's status and no-ops instead of starting. This means a Stop click
takes effect at the next task boundary, not instantly mid-task — honest about that
limitation rather than pretending it's immediate, since it isn't under this pool type.
POST /documents/{id}/cancel (routes_status.py) sets status="failed" with a
"Cancelled by user" reason; this check is simply "is this document already marked
failed by the time I'm about to start," reusing the same terminal state a real
failure would reach rather than inventing a separate "cancelled" status/migration.
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


def not_cancelled(document) -> bool:
    """True if this task should proceed. False if the document has already been
    marked failed (either a real failure or a user-initiated cancel — this check
    doesn't need to tell the difference, since either way there's nothing to do).
    Takes an already-fetched Document rather than re-querying, since every call site
    already has one in hand for its own purposes.
    """
    return document is not None and document.status != "failed"
