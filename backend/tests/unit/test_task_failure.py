"""app.workers._failure.mark_document_failed — the shared helper every chain-link task
(tasks_ingest.py, tasks_chunk.py, tasks_pipeline.py) calls on terminal failure. No
broker, no real DB (CLAUDE.md hard rule 8).
"""

from unittest.mock import MagicMock, patch

from app.workers._failure import mark_document_failed

FAKE_DOC_ID = "11111111-1111-1111-1111-111111111111"


def test_sets_status_failed_and_the_reason() -> None:
    with patch("app.workers._failure.SessionLocal") as mock_session_local:
        db = mock_session_local.return_value
        document = MagicMock()
        db.get.return_value = document

        mark_document_failed(FAKE_DOC_ID, "something broke")

        assert document.status == "failed"
        assert document.failure_reason == "something broke"
        db.commit.assert_called_once()
        db.close.assert_called_once()


def test_does_nothing_if_the_document_no_longer_exists() -> None:
    with patch("app.workers._failure.SessionLocal") as mock_session_local:
        db = mock_session_local.return_value
        db.get.return_value = None

        mark_document_failed(FAKE_DOC_ID, "something broke")

        db.commit.assert_not_called()
        db.close.assert_called_once()
