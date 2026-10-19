"""ingest_document_task's own retry/failure-handling, not app.services.ingestion
itself (covered elsewhere) — the real, previously-missing failure path a genuinely
stuck tender exposed: a plain `chain(...)` link (docs/DECISIONS.md) with no chord to
fall back on, so exhausting retries here previously left the document silently stuck
at whatever status ingestion last reached, forever, with zero signal anywhere. No
broker, no real DB — mocks SessionLocal and ingestion.run_ingestion directly (CLAUDE.md
hard rule 8).

Same `.run(...)` pattern as test_tasks_chunk.py — see that file's docstring for why
calling the task directly doesn't let push_request(retries=N) stick.
"""

from unittest.mock import patch

import app.workers.celery_app  # noqa: F401
from app.workers.tasks_ingest import ingest_document_task

FAKE_DOC_ID = "11111111-1111-1111-1111-111111111111"


def test_retries_when_attempts_remain() -> None:
    ingest_document_task.push_request(retries=0)
    try:
        with (
            patch("app.workers.tasks_ingest.SessionLocal") as mock_session_local,
            patch("app.services.ingestion.run_ingestion", side_effect=ValueError("boom")),
            patch.object(
                ingest_document_task, "retry", side_effect=RuntimeError("retried")
            ) as mock_retry,
            patch("app.workers.tasks_ingest.mark_document_failed") as mock_mark_failed,
        ):
            try:
                ingest_document_task.run(FAKE_DOC_ID)
            except RuntimeError:
                pass

            mock_retry.assert_called_once()
            mock_mark_failed.assert_not_called()
            mock_session_local.return_value.rollback.assert_called_once()
    finally:
        ingest_document_task.pop_request()


def test_marks_document_failed_once_retries_are_exhausted() -> None:
    # max_retries=3 on the real task; retries=3 means retries < max_retries is False.
    ingest_document_task.push_request(retries=3)
    try:
        with (
            patch("app.workers.tasks_ingest.SessionLocal") as mock_session_local,
            patch(
                "app.services.ingestion.run_ingestion",
                side_effect=ConnectionError("provider timed out"),
            ),
            patch.object(ingest_document_task, "retry") as mock_retry,
            patch("app.workers.tasks_ingest.mark_document_failed") as mock_mark_failed,
        ):
            raised = False
            try:
                ingest_document_task.run(FAKE_DOC_ID)
            except ConnectionError:
                raised = True

            assert raised, "original exception must propagate so Celery marks the task failed"
            mock_retry.assert_not_called()
            mock_mark_failed.assert_called_once()
            call_args = mock_mark_failed.call_args
            assert call_args[0][0] == FAKE_DOC_ID
            assert "3 retries" in call_args[0][1]
            assert "provider timed out" in call_args[0][1]
            mock_session_local.return_value.rollback.assert_called_once()
    finally:
        ingest_document_task.pop_request()
