"""build_chunks_task's own retry/failure-handling, not app.pipeline.chunk.build_chunks
itself (covered elsewhere) — a plain `chain(...)` link (docs/DECISIONS.md), so unlike
map_pass_chunk_task's chord-header exemption (#62), exhausting retries here must
explicitly mark the document failed or the chain just stops silently with nothing
ever reaching status="failed". No broker, no real DB — mocks SessionLocal and
app.workers._failure.mark_document_failed directly (CLAUDE.md hard rule 8).

Calls `.run(...)` (the raw task function), not the task directly: calling a bound
task directly (`build_chunks_task(...)`) goes through Celery's own `__call__`, which
pushes its OWN fresh request context (always retries=0) around the call, silently
shadowing any `push_request(retries=N)` set up beforehand — `.run()` skips that
wrapping, so a manually pushed context stays the one `self.request` actually reads.

Import order matters (circular, see other tasks_* test files): importing celery_app
first, fully, avoids hitting tasks_chunk mid-init.
"""

from unittest.mock import patch

import app.workers.celery_app  # noqa: F401
from app.workers.tasks_chunk import build_chunks_task

FAKE_DOC_ID = "11111111-1111-1111-1111-111111111111"


def test_retries_when_attempts_remain() -> None:
    build_chunks_task.push_request(retries=0)
    try:
        with (
            patch("app.workers.tasks_chunk.SessionLocal") as mock_session_local,
            patch.object(
                build_chunks_task, "retry", side_effect=RuntimeError("retried")
            ) as mock_retry,
            patch("app.workers.tasks_chunk.mark_document_failed") as mock_mark_failed,
        ):
            db = mock_session_local.return_value
            db.get.return_value = None  # Document not found -> raises inside the task

            try:
                build_chunks_task.run(FAKE_DOC_ID)
            except RuntimeError:
                pass

            mock_retry.assert_called_once()
            mock_mark_failed.assert_not_called()
    finally:
        build_chunks_task.pop_request()


def test_marks_document_failed_once_retries_are_exhausted() -> None:
    # max_retries=3 on the real task; retries=3 means retries < max_retries is False.
    build_chunks_task.push_request(retries=3)
    try:
        with (
            patch("app.workers.tasks_chunk.SessionLocal") as mock_session_local,
            patch.object(build_chunks_task, "retry") as mock_retry,
            patch("app.workers.tasks_chunk.mark_document_failed") as mock_mark_failed,
        ):
            db = mock_session_local.return_value
            db.get.return_value = None

            raised = False
            try:
                build_chunks_task.run(FAKE_DOC_ID)
            except ValueError:
                raised = True

            assert raised, "original exception must propagate so Celery marks the task failed"
            mock_retry.assert_not_called()
            mock_mark_failed.assert_called_once()
            call_args = mock_mark_failed.call_args
            assert call_args[0][0] == FAKE_DOC_ID
            assert "3 retries" in call_args[0][1]
            db.rollback.assert_called_once()
    finally:
        build_chunks_task.pop_request()
