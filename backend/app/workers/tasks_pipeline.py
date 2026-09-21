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

from app.storage.db import SessionLocal
from app.workers.celery_app import celery_app
from app.workers.tasks_chunk import build_chunks_task
from app.workers.tasks_ingest import ingest_document_task
from app.workers.tasks_map import map_pass_chunk_task
from app.workers.tasks_reduce import go_no_go_task, risk_finder_task, synopsis_task


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
    """
    from app.models.document import Document

    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        document.status = "analyzing"
        db.commit()
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        raise self.retry(exc=exc) from exc
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


@celery_app.task(name="start_reduce_pass_for_document", bind=True)
def _start_reduce_pass(self, map_results: list[str], document_id: str) -> None:
    """Chord callback — every chunk's map pass has completed (or exhausted its own
    retries; a chord callback still fires on partial failure, since Celery's default
    error handling for a chord is to propagate to the callback rather than silently
    hang it forever). Fans the three reduce-pass modules out as their own independent
    group, then marks the document "ready" once all three finish.
    """
    chord(
        group(
            go_no_go_task.s(document_id),
            synopsis_task.s(document_id),
            risk_finder_task.s(document_id),
        ),
        _mark_document_ready.s(document_id),
    ).delay()


@celery_app.task(name="mark_document_ready", bind=True)
def _mark_document_ready(self, reduce_results: list[str], document_id: str) -> None:
    from app.models.document import Document

    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is not None:
            document.status = "ready"
            db.commit()
    finally:
        db.close()
