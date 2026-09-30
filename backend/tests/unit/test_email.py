"""Unit tests for app.core.email — smtplib itself is always mocked (no real network
call, CLAUDE.md hard rule 8); a real send is manual/integration-only.
"""

from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.core.email import send_review_notification


def test_noops_when_smtp_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_username", "")

    with patch("app.core.email.smtplib.SMTP") as mock_smtp:
        send_review_notification(
            document_id="doc-1",
            criterion="ISO 9001 certification",
            required="ISO 9001:2015",
            company_value="No relevant information",
            reviewer_note="Certificate on file",
        )

    mock_smtp.assert_not_called()


def test_sends_via_smtp_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "bot@example.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    monkeypatch.setattr(settings, "smtp_from_address", "bot@example.com")
    monkeypatch.setattr(settings, "review_notification_email", "reviewer@example.com")

    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server
    with patch("app.core.email.smtplib.SMTP", return_value=mock_server) as mock_smtp:
        send_review_notification(
            document_id="doc-1",
            criterion="ISO 9001 certification",
            required="ISO 9001:2015",
            company_value="No relevant information",
            reviewer_note="Certificate on file",
        )

    mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("bot@example.com", "app-password")
    mock_server.send_message.assert_called_once()
    sent_message = mock_server.send_message.call_args[0][0]
    assert sent_message["To"] == "reviewer@example.com"
    assert "ISO 9001 certification" in sent_message["Subject"]
    assert "Certificate on file" in sent_message.get_payload()


def test_retries_then_gives_up_without_raising(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_username", "bot@example.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")

    with (
        patch("app.core.email.smtplib.SMTP", side_effect=OSError("connection refused")),
        patch("app.core.email.time.sleep") as mock_sleep,
    ):
        send_review_notification(
            document_id="doc-1",
            criterion="ISO 9001 certification",
            required="ISO 9001:2015",
            company_value="No relevant information",
            reviewer_note=None,
        )

    # MAX_RETRIES=2 -> 2 sleeps between the 3 attempts, then gives up silently
    assert mock_sleep.call_count == 2


def test_missing_reviewer_note_falls_back_to_placeholder_text(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_username", "bot@example.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    monkeypatch.setattr(settings, "review_notification_email", "reviewer@example.com")

    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server
    with patch("app.core.email.smtplib.SMTP", return_value=mock_server):
        send_review_notification(
            document_id="doc-1",
            criterion="ISO 9001 certification",
            required="ISO 9001:2015",
            company_value="No relevant information",
            reviewer_note=None,
        )

    sent_message = mock_server.send_message.call_args[0][0]
    assert "(none provided)" in sent_message.get_payload()
