"""The orchestration tasks in tasks_pipeline.py's own failure handling — not the
reduce-pass/map-pass logic they fan out to (covered elsewhere). `_start_map_and_reduce`
is the last `chain(...)` link (docs/DECISIONS.md); `_start_reduce_pass` and
`_mark_document_ready` are chord callbacks with no retry of their own, so any failure
in them is terminal immediately. All three previously had no path to status="failed"
at all — this is the real, previously-missing safety net a genuinely stuck tender
exposed. No broker, no real DB — mocks SessionLocal, chord/group dispatch, and
app.workers._failure.mark_document_failed directly (CLAUDE.md hard rule 8).

Same `.run(...)` pattern as test_tasks_chunk.py — see that file's docstring for why
calling a bound task directly doesn't let push_request(retries=N) stick.
"""

from unittest.mock import MagicMock, patch

import app.workers.celery_app  # noqa: F401
from app.workers.tasks_pipeline import (
    _mark_document_ready,
    _start_map_and_reduce,
    _start_reduce_pass,
)

FAKE_DOC_ID = "11111111-1111-1111-1111-111111111111"


def test_start_map_and_reduce_retries_when_attempts_remain() -> None:
    _start_map_and_reduce.push_request(retries=0)
    try:
        with (
            patch("app.workers.tasks_pipeline.SessionLocal") as mock_session_local,
            patch.object(
                _start_map_and_reduce, "retry", side_effect=RuntimeError("retried")
            ) as mock_retry,
            patch("app.workers.tasks_pipeline.mark_document_failed") as mock_mark_failed,
        ):
            mock_session_local.return_value.get.return_value = None  # -> ValueError inside

            try:
                _start_map_and_reduce.run(["chunk-1"], FAKE_DOC_ID)
            except RuntimeError:
                pass

            mock_retry.assert_called_once()
            mock_mark_failed.assert_not_called()
    finally:
        _start_map_and_reduce.pop_request()


def test_start_map_and_reduce_marks_failed_once_exhausted() -> None:
    _start_map_and_reduce.push_request(retries=3)
    try:
        with (
            patch("app.workers.tasks_pipeline.SessionLocal") as mock_session_local,
            patch.object(_start_map_and_reduce, "retry") as mock_retry,
            patch("app.workers.tasks_pipeline.mark_document_failed") as mock_mark_failed,
        ):
            mock_session_local.return_value.get.return_value = None

            raised = False
            try:
                _start_map_and_reduce.run(["chunk-1"], FAKE_DOC_ID)
            except ValueError:
                raised = True

            assert raised
            mock_retry.assert_not_called()
            mock_mark_failed.assert_called_once()
            assert mock_mark_failed.call_args[0][0] == FAKE_DOC_ID
    finally:
        _start_map_and_reduce.pop_request()


def test_start_map_and_reduce_skips_to_reduce_on_zero_chunks() -> None:
    """A document with no chunks must not hang "analyzing" forever with no chord to
    fire — this already worked before this change; guarded here so the new try/except
    wrapping around it doesn't accidentally break the zero-chunk short-circuit.
    """
    with (
        patch("app.workers.tasks_pipeline.SessionLocal") as mock_session_local,
        patch("app.workers.tasks_pipeline._start_reduce_pass") as mock_reduce_pass,
    ):
        document = MagicMock()
        mock_session_local.return_value.get.return_value = document

        _start_map_and_reduce.run([], FAKE_DOC_ID)

        assert document.status == "analyzing"
        mock_reduce_pass.delay.assert_called_once_with([], FAKE_DOC_ID)


def test_start_reduce_pass_marks_failed_on_dispatch_error() -> None:
    with (
        patch("app.workers.tasks_pipeline.chord", side_effect=RuntimeError("broker down")),
        patch("app.workers.tasks_pipeline.mark_document_failed") as mock_mark_failed,
    ):
        raised = False
        try:
            _start_reduce_pass.run([], FAKE_DOC_ID)
        except RuntimeError:
            raised = True

        assert raised, "original exception must propagate so Celery marks the task failed"
        mock_mark_failed.assert_called_once()
        assert mock_mark_failed.call_args[0][0] == FAKE_DOC_ID


def test_mark_document_ready_marks_failed_on_commit_error() -> None:
    with (
        patch("app.workers.tasks_pipeline.SessionLocal") as mock_session_local,
        patch("app.workers.tasks_pipeline.mark_document_failed") as mock_mark_failed,
    ):
        db = mock_session_local.return_value
        document = MagicMock()
        db.get.return_value = document
        db.commit.side_effect = RuntimeError("db write failed")

        raised = False
        try:
            _mark_document_ready.run([], FAKE_DOC_ID)
        except RuntimeError:
            raised = True

        assert raised
        mock_mark_failed.assert_called_once()
        db.rollback.assert_called_once()


def test_mark_document_ready_happy_path_unaffected() -> None:
    with (
        patch("app.workers.tasks_pipeline.SessionLocal") as mock_session_local,
        patch("app.workers.tasks_pipeline.mark_document_failed") as mock_mark_failed,
    ):
        db = mock_session_local.return_value
        document = MagicMock()
        db.get.return_value = document

        _mark_document_ready.run([], FAKE_DOC_ID)

        assert document.status == "ready"
        db.commit.assert_called_once()
        mock_mark_failed.assert_not_called()
