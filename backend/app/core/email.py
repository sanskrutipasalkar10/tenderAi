"""Outbound email — currently exactly one use: notifying the configured recipient
(review_notification_email, default sanskruti.pasalkar@c4i4.org) when a bid-team
member marks a Go/No-Go criterion eligible during human review (docs/DECISIONS.md),
flagging the gap for manual entry into the company profile so the same tender-analysis
gap doesn't recur. Plain smtplib (Python stdlib) — no new dependency, same
"hand-rolled over a library" preference already established for app.llm.client (never
litellm) and app.pipeline.fetch_links.fetch_url, for the same reason: explicit control
over timeout/retry behavior rather than trusting a library's defaults.

No-ops cleanly (logs and returns) when SMTP isn't configured, matching
app.core.tracing's Langfuse no-op pattern — a missing SMTP config must never block the
review action itself; this is a best-effort side notification, not the primary action.
"""

import random
import smtplib
import time
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 2
CONNECT_TIMEOUT_SECONDS = 10


def send_review_notification(
    *,
    document_id: str,
    criterion: str,
    required: str,
    company_value: str,
    reviewer_note: str | None,
) -> None:
    """Called from routes_analysis.py's review endpoint after a "pass" override is
    saved. Never raises — a failed send is logged, not surfaced to the caller, since
    the review itself already succeeded and must not be undone or reported as failed
    over a notification email (hard rule 10's timeout/retry applies, but a send
    failure here is never allowed to become a 500 for the reviewer).
    """
    if not settings.smtp_host or not settings.smtp_username:
        logger.info("email.smtp_not_configured", document_id=document_id)
        return

    subject = f"Company profile update needed — {criterion}"
    body = (
        "A bid-team member marked the following criterion eligible during human "
        f"review of tender {document_id}, based on information not yet reflected in "
        "the company profile database. Please review and add the supporting "
        "document/data to the company profile so future tender analyses don't hit "
        "the same gap.\n\n"
        f"Criterion: {criterion}\n"
        f"Tender requirement: {required}\n"
        f"Company profile currently shows: {company_value}\n"
        f"Reviewer's note: {reviewer_note or '(none provided)'}\n"
    )
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address or settings.smtp_username
    message["To"] = settings.review_notification_email

    for attempt in range(MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=CONNECT_TIMEOUT_SECONDS
            ) as server:
                server.starttls()
                server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
            logger.info(
                "email.review_notification_sent", document_id=document_id, criterion=criterion
            )
            return
        except Exception as exc:  # noqa: BLE001 - a send failure must never propagate
            if attempt == MAX_RETRIES:
                logger.warning(
                    "email.send_failed",
                    document_id=document_id,
                    criterion=criterion,
                    error=str(exc),
                )
                return
            backoff = (2**attempt) + random.uniform(0, 1)
            logger.warning(
                "email.retry", attempt=attempt, backoff_seconds=round(backoff, 2), error=str(exc)
            )
            time.sleep(backoff)
