"""GET /documents/{id}/status — main_document_pages/linked_documents_found
(docs/DECISIONS.md #75/#77) split cleanly from pages_processed so the frontend never
shows a nonsensical "48/6 pages processed" ratio while a hyperlinked document's links
are still being fetched. All computed live from `pages` (no new table/column).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.document import Document

client = TestClient(app)


def _override_db(scalars: list[int]):
    """Returns a fake db whose db.execute(...).scalar_one() yields each of `scalars`
    in order — matches the exact sequence of queries get_document_status issues.
    """
    fake_db = MagicMock()
    results = iter(scalars)
    fake_db.execute.return_value.scalar_one.side_effect = lambda: next(results)
    fake_db.execute.return_value.scalars.return_value = []
    return fake_db


def setup_module(_module) -> None:
    app.dependency_overrides[get_current_user] = lambda: "test-user"


def teardown_module(_module) -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_status_splits_main_document_pages_from_linked_documents_found() -> None:
    document_id = uuid.uuid4()
    document = Document(
        id=document_id, filename="GeM-Bidding-x.pdf", status="analyzing", total_pages=68,
        updated_at=datetime.now(timezone.utc),
    )
    fake_db = MagicMock()
    fake_db.get.return_value = document
    # Order matches routes_status.py: pages_processed, main_document_pages,
    # linked_documents_found, attachments_processed, chunks_total, chunks_mapped.
    scalars = iter([48, 6, 2, 1, 22, 9])
    fake_db.execute.return_value.scalar_one.side_effect = lambda: next(scalars)
    fake_db.execute.return_value.scalars.return_value = []
    app.dependency_overrides[get_db] = lambda: fake_db

    response = client.get(f"/documents/{document_id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["pages_processed"] == 48
    assert body["main_document_pages"] == 6
    assert body["linked_documents_found"] == 2
    assert body["attachments_processed"] == 1
    assert body["total_pages"] == 68
