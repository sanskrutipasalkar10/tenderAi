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
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 422
    assert "PDF" in response.json()["message"]


def test_upload_rejects_empty_file() -> None:
    response = client.post(
        "/documents",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 422
    assert "empty" in response.json()["message"].lower()


def test_upload_rejects_oversized_file() -> None:
    from app.core.config import settings

    oversized = b"x" * (settings.max_upload_size_mb * 1024 * 1024 + 1)
    response = client.post(
        "/documents",
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
        files={"file": ("memo.pdf", io.BytesIO(non_tender_pdf), "application/pdf")},
    )
    assert response.status_code == 422
    assert "tender" in response.json()["message"].lower()


@patch("app.api.routes_ingest.ingest_document_task")
@patch("app.api.routes_ingest.upload_pdf")
def test_valid_upload_enqueues_ingestion_task(mock_upload_pdf, mock_task, _override_db) -> None:
    mock_upload_pdf.return_value = "documents/fake/original.pdf"

    response = client.post(
        "/documents",
        files={"file": ("tender.pdf", io.BytesIO(VALID_FIXTURE_PDF), "application/pdf")},
    )

    assert response.status_code == 201
    mock_upload_pdf.assert_called_once()
    mock_task.delay.assert_called_once()


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
