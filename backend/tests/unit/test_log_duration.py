import pytest
import structlog
from structlog.testing import capture_logs

from app.core.logging import log_duration


def test_log_duration_logs_ok_outcome_with_duration_and_fields():
    logger = structlog.get_logger("test")
    with capture_logs() as logs:
        with log_duration(logger, "stage.example", document_id="doc-1"):
            pass

    assert len(logs) == 1
    assert logs[0]["event"] == "stage.example"
    assert logs[0]["outcome"] == "ok"
    assert logs[0]["document_id"] == "doc-1"
    assert logs[0]["duration_seconds"] >= 0


def test_log_duration_still_logs_and_reraises_on_error():
    logger = structlog.get_logger("test")
    with capture_logs() as logs:
        with pytest.raises(RuntimeError):
            with log_duration(logger, "stage.example"):
                raise RuntimeError("boom")

    assert logs[0]["outcome"] == "error"
