"""Route-level tests for GET /documents/{id}/pages/{n} and its /image sibling — the
citation-verification UI's actual data source (docs/SPEC.md's HITL note).
"""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.page import Page

client = TestClient(app)


def _make_page(**overrides) -> Page:
    defaults = dict(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_number=3,
        classification="native_text",
        extraction_method="native",
        raw_text="Bid submission deadline: 15 Nov 2026",
        confidence_score=1.0,
        image_s3_key=None,
    )
    defaults.update(overrides)
    return Page(**defaults)


@pytest.fixture(autouse=True)
def _overrides():
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    yield fake_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_get_page_content_returns_real_text_and_flags_no_image(_overrides) -> None:
    page = _make_page()
    _overrides.query.return_value.filter.return_value.first.return_value = page

    response = client.get(f"/documents/{page.document_id}/pages/3")

    assert response.status_code == 200
    body = response.json()
    assert body["page_number"] == 3
    assert body["raw_text"] == "Bid submission deadline: 15 Nov 2026"
    assert body["has_image"] is False


def test_get_page_content_flags_has_image_true_when_image_s3_key_set(_overrides) -> None:
    page = _make_page(
        image_s3_key="documents/doc-1/pages/00003.png", classification="scanned_image"
    )
    _overrides.query.return_value.filter.return_value.first.return_value = page

    response = client.get(f"/documents/{page.document_id}/pages/3")

    assert response.json()["has_image"] is True


def test_get_page_content_404s_for_a_nonexistent_page(_overrides) -> None:
    _overrides.query.return_value.filter.return_value.first.return_value = None

    response = client.get(f"/documents/{uuid.uuid4()}/pages/999")

    assert response.status_code == 404


def test_get_page_image_404s_when_page_has_no_image(_overrides) -> None:
    page = _make_page(image_s3_key=None)
    _overrides.query.return_value.filter.return_value.first.return_value = page

    response = client.get(f"/documents/{page.document_id}/pages/3/image")

    assert response.status_code == 404
    assert "no rendered image" in response.json()["detail"].lower()


def test_get_page_image_returns_real_bytes_with_png_content_type(_overrides, monkeypatch) -> None:
    page = _make_page(image_s3_key="documents/doc-1/pages/00003.png")
    _overrides.query.return_value.filter.return_value.first.return_value = page
    monkeypatch.setattr(
        "app.api.routes_pages.get_object_bytes", lambda key: b"\x89PNG\r\n\x1a\nfake-png-bytes"
    )

    response = client.get(f"/documents/{page.document_id}/pages/3/image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG\r\n\x1a\nfake-png-bytes"


def test_page_routes_require_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.get(f"/documents/{uuid.uuid4()}/pages/3")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: "test-user"
