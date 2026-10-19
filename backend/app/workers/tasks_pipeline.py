"""Orchestrates the full pipeline as one Celery workflow: ingest -> chunk -> map pass
(fanned out, one task per chunk) -> reduce pass (fanned out, one task per module) ->
status="ready". Until this file existed, `POST /documents` only ever enqueued
`ingest_document_task` — chunking/map/reduce were fully built and individually
tested but nothing actually chained them together after ingestion finished, so a real
upload never progressed past `status="extracted"`. See tasks_chunk.py's own docstring,
which already anticipated this file's existence, and docs/DECISIONS.md for the phases
that built each stage this wires together.

Two Celery primitives beyond a plain chain do the fan-out/fan-in:
- `chord(header, callback)` runs every task in `header` (a `group`) in parallel, then
  calls `callback` once ALL of them have finished (successfully or via exhausted
  retries) — this is exactly "map, then reduce" at the Celery level, not just this
  pipeline's own domain-level map/reduce naming.
- `group(...)` runs its tasks independently and in parallel with no ordering
  guarantee and no dependency between them — used for the three reduce-pass modules
  (tasks_reduce.py's own docstring: one module's failure must not block the others).
"""

import uuid

from celery import chain, chord, group

from app.core.logging import get_logger
from app.storage.db import SessionLocal
from app.workers._failure import mark_document_failed
from app.workers.celery_app import celery_app
from app.workers.tasks_chunk import build_chunks_task
from app.workers.tasks_ingest import ingest_document_task
from app.workers.tasks_map import map_pass_chunk_task
from app.workers.tasks_reduce import go_no_go_task, risk_finder_task, synopsis_task

logger = get_logger(__name__)


def enqueue_full_pipeline(document_id: str) -> None:
    """Entry point called from routes_ingest.py in place of the old bare
    `ingest_document_task.delay(...)`. Builds and enqueues the whole chain; returns
    immediately (per docs/SPEC.md's "completeness over speed, but the API doesn't
    block" priority) — nothing here is awaited.
    """
    workflow = chain(
        ingest_document_task.s(document_id),
        # .si() (immutable signature): ingest_document_task returns None, and
        # build_chunks_task takes only document_id — don't let chain() try to prepend
        # that None as an extra positional argument.
        build_chunks_task.si(document_id),
        _start_map_and_reduce.s(document_id),
    )
    workflow.delay()


def enqueue_reevaluation(document_id: str) -> None:
    """Entry point called from routes_analysis.py's "Reevaluate" action — re-runs only
    the reduce pass (go_no_go, synopsis, risk_finder) against this document's existing
    chunk_extractions, for when the company profile or reduce-pass prompts/logic have
    changed since the document was last analyzed. Deliberately skips ingestion and the
    map pass: the source PDF hasn't changed, so its already-extracted facts are still
    valid, and re-paying for vision/extraction LLM calls would be wasted cost and time
    for data that didn't need to change.

    `_start_reduce_pass`'s `map_results` argument is never read by its body (it only
    exists because that function doubles as a chord callback during the normal
    pipeline) — an empty list here is a safe placeholder, not a real chord result.
    """
    _start_reduce_pass.delay([], document_id)


@celery_app.task(
    name="start_map_and_reduce_for_document",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def _start_map_and_reduce(self, chunk_ids: list[str], document_id: str) -> None:
    """Runs once chunking has finished. Marks the document "analyzing" (the existing
    DocumentStatus enum has no separate "chunking"/"mapping" state — see
    docs/SPEC.md's DDL, applied as-is), then fans the map pass out as a chord: every
    chunk's map-pass task runs in parallel, and once ALL of them finish,
    `_start_reduce_pass` (the chord's callback) fires automatically.

    The last `chain(...)` link (docs/DECISIONS.md #62's chord-header exemption doesn't
    apply here) — on exhausted retries this must explicitly mark the document failed,
    or a dead status-write/chord-dispatch here silently strands the document at
    status="extracted" forever.
    """
    from app.models.document import Document

    try:
        db = SessionLocal()
        try:
            document = db.get(Document, uuid.UUID(document_id))
            if document is None:
                raise ValueError(f"Document {document_id} not found")
            document.status = "analyzing"
            db.commit()
        finally:
            db.close()

        if not chunk_ids:
            # A document with zero chunks (shouldn't happen for a real tender, but a
            # near-empty/edge-case upload could produce one) has nothing to map — skip
            # straight to reduce so it doesn't hang "analyzing" forever with no chord to
            # ever fire.
            _start_reduce_pass.delay([], document_id)
            return

        chord(
            group(map_pass_chunk_task.s(chunk_id) for chunk_id in chunk_ids),
            _start_reduce_pass.s(document_id),
        ).delay()
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        logger.error(
            "pipeline.start_map_and_reduce_permanently_failed",
            document_id=document_id,
            error=str(exc),
        )
        mark_document_failed(
            document_id, f"Starting map/reduce failed after {self.max_retries} retries: {exc}"
        )
        raise


@celery_app.task(name="start_reduce_pass_for_document", bind=True)
def _start_reduce_pass(self, map_results: list[str], document_id: str) -> None:
    """Chord callback — every chunk's map pass has completed (or exhausted its own
    retries; a chord callback still fires on partial failure, since Celery's default
    error handling for a chord is to propagate to the callback rather than silently
    hang it forever). Fans the three reduce-pass modules out as their own independent
    group, then marks the document "ready" once all three finish.

    This task has no `max_retries` of its own (it's a chord callback, not a chain
    link — Celery doesn't retry a chord callback the same way), so any failure here
    (e.g. a broker blip while enqueuing the reduce chord) is terminal immediately;
    caught and marked failed rather than left silently stuck at status="analyzing"
    forever with the map pass already fully done.
    """
    try:
        chord(
            group(
                go_no_go_task.s(document_id),
                synopsis_task.s(document_id),
                risk_finder_task.s(document_id),
            ),
            _mark_document_ready.s(document_id),
        ).delay()
    except Exception as exc:  # noqa: BLE001 - nothing to retry into; this chord has no caller left
        logger.error(
            "pipeline.start_reduce_pass_failed", document_id=document_id, error=str(exc)
        )
        mark_document_failed(document_id, f"Starting reduce pass failed: {exc}")
        raise


@celery_app.task(name="mark_document_ready", bind=True)
def _mark_document_ready(self, reduce_results: list[str], document_id: str) -> None:
    from app.models.document import Document

    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is not None:
            document.status = "ready"
            db.commit()
    except Exception as exc:  # noqa: BLE001 - last step in the chain; nothing left to retry into
        db.rollback()
        logger.error("pipeline.mark_ready_failed", document_id=document_id, error=str(exc))
        mark_document_failed(document_id, f"Failed to mark document ready: {exc}")
        raise
    finally:
        db.close()
