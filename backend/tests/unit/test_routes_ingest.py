"""Route-level tests for the parts of /documents that don't need a real Postgres:
upload validation (content-type/size) fails before any DB write, and status-lookup
handles the "not found" path. The full happy-path (upload → persisted Document with a
real generated UUID → Celery enqueue) needs a live database and belongs in
tests/integration/ once one is available (colleague's Postgres, per docs/DECISIONS.md) —
faking a DB round-trip here would just test the fake, not the route.
"""

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app

client = TestClient(app)

# company_profile_id is now a required query param (docs/DECISIONS.md) — every upload
# test below needs one. The fake DB's db.get() returns a plain MagicMock (truthy, not
# None) for any arguments by default, so this doesn't need its own explicit mock
# unless a test specifically wants the "profile not found" 404 path.
FAKE_COMPANY_PROFILE_ID = uuid.uuid4()
UPLOAD_PARAMS = {"company_profile_id": str(FAKE_COMPANY_PROFILE_ID)}

# A real, small, genuinely tender-like fixture — Phase 6 wires app.guardrails.
# input_checks.validate_upload into this route for real, so "a valid PDF upload"
# now means a real PDF that also passes the "is this a tender" heuristic, not
# just PDF-shaped bytes.
VALID_FIXTURE_PDF = (
    Path(__file__).parent.parent.parent
    / "evals"
    / "fixtures"
    / "pdfs"
    / "fixture_01_nhai_road.pdf"
).read_bytes()


def _fake_refresh(obj) -> None:
    """Stands in for what a real flush/refresh against Postgres would populate
    (server-generated id, uploaded_at) — there's no live DB in this environment yet.
    """
    if getattr(obj, "id", None) is None:
        obj.id = uuid.uuid4()
    if getattr(obj, "uploaded_at", None) is None:
        obj.uploaded_at = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _override_db():
    fake_db = MagicMock()
    fake_db.refresh.side_effect = _fake_refresh
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    yield fake_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_upload_rejects_non_pdf_content_type() -> None:
    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 422
    assert "PDF" in response.json()["message"]


def test_upload_rejects_empty_file() -> None:
    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 422
    assert "empty" in response.json()["message"].lower()


def test_upload_rejects_oversized_file() -> None:
    from app.core.config import settings

    oversized = b"x" * (settings.max_upload_size_mb * 1024 * 1024 + 1)
    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={"file": ("big.pdf", io.BytesIO(oversized), "application/pdf")},
    )
    assert response.status_code == 422
    assert "limit" in response.json()["message"].lower()


def test_upload_rejects_content_that_does_not_look_like_a_tender() -> None:
    # A structurally valid but content-free PDF — real bytes fitz can open, but with
    # no tender-signal terms on the first few pages.
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "This is just a random memo about lunch.")
    non_tender_pdf = doc.tobytes()
    doc.close()

    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={"file": ("memo.pdf", io.BytesIO(non_tender_pdf), "application/pdf")},
    )
    assert response.status_code == 422
    assert "tender" in response.json()["message"].lower()


def test_upload_requires_company_profile_id() -> None:
    response = client.post(
        "/documents",
        files={"file": ("tender.pdf", io.BytesIO(VALID_FIXTURE_PDF), "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_404s_when_company_profile_not_found(_override_db) -> None:
    _override_db.get.return_value = None
    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={"file": ("tender.pdf", io.BytesIO(VALID_FIXTURE_PDF), "application/pdf")},
    )
    assert response.status_code == 404


@patch("app.api.routes_ingest.enqueue_full_pipeline")
@patch("app.api.routes_ingest.upload_pdf")
def test_valid_upload_enqueues_ingestion_task(mock_upload_pdf, mock_enqueue, _override_db) -> None:
    mock_upload_pdf.return_value = "documents/fake/original.pdf"

    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={"file": ("tender.pdf", io.BytesIO(VALID_FIXTURE_PDF), "application/pdf")},
    )

    assert response.status_code == 201
    mock_upload_pdf.assert_called_once()
    mock_enqueue.assert_called_once()


# --- supporting-document attachments (docs/DECISIONS.md — migration 0005) -----------


def _small_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_upload_rejects_non_pdf_attachment() -> None:
    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={
            "file": ("tender.pdf", io.BytesIO(VALID_FIXTURE_PDF), "application/pdf"),
            "attachments": ("certificate.txt", io.BytesIO(b"hello"), "text/plain"),
        },
    )
    assert response.status_code == 422
    assert "certificate.txt" in response.json()["message"]
    assert "PDF" in response.json()["message"]


def test_upload_rejects_empty_attachment() -> None:
    response = client.post(
        "/documents",
        params=UPLOAD_PARAMS,
        files={
            "file": ("tender.pdf", io.BytesIO(VALID_FIXTURE_PDF), "application/pdf"),
            "attachments": ("empty.pdf", io.BytesIO(b""), "application/pdf"),
        },
    )
    assert response.status_code == 422
    assert "empty" in response.json()["message"].lower()


def test_upload_accepts_an_attachment_that_would_fail_the_tender_heuristic() -> None:
    """A supporting document (a certificate, a past-project reference) legitimately
    isn't a tender itself and must not be rejected for not looking like one — the
    user confirmed this scope explicitly, so an attachment goes through
    validate_attachment (basic PDF sanity), never validate_upload's
    looks_like_a_tender check.
    """
    with (
        patch("app.api.routes_ingest.enqueue_full_pipeline"),
        patch("app.api.routes_ingest.upload_pdf", return_value="documents/fake/original.pdf"),
        patch(
            "app.api.routes_ingest.upload_attachment_pdf",
            return_value="documents/fake/attachments/x/original.pdf",
        ) as mock_upload_attachment,
    ):
        response = client.post(
            "/documents",
            params=UPLOAD_PARAMS,
            files={
                "file": ("tender.pdf", io.BytesIO(VALID_FIXTURE_PDF), "application/pdf"),
                "attachments": (
                    "iso_certificate.pdf",
                    io.BytesIO(_small_pdf("ISO 9001:2015 Certificate of Registration")),
                    "application/pdf",
                ),
            },
        )

    assert response.status_code == 201
    mock_upload_attachment.assert_called_once()


def test_status_returns_404_for_unknown_document(_override_db) -> None:
    _override_db.get.return_value = None
    response = client.get(f"/documents/{uuid.uuid4()}/status")
    assert response.status_code == 404


def test_protected_route_rejects_missing_token() -> None:
    app.dependency_overrides.pop(get_current_user, None)  # this test wants the real dependency
    try:
        response = client.get(f"/documents/{uuid.uuid4()}/status")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: "test-user"
