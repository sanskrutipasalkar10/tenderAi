"""app.services.ingestion's new hyperlinked-document stage (docs/DECISIONS.md) — a
cover PDF's own pages plus whatever its links resolve to, appended as more `pages` rows
on the same document with page_number continuing past the cover PDF's own page count.
Mocks fetch_links entirely (no real network calls, CLAUDE.md hard rule 8) — real
fetch/extraction correctness against the actual GeM sample PDFs is verified separately,
outside the committed test suite (those PDFs are real, gitignored tender documents,
docs/DECISIONS.md #27, never something a test can depend on existing).
"""

import uuid
from unittest.mock import patch

import fitz
import pytest
from moto import mock_aws

from app.core.config import settings
from app.models.document import Document
from app.models.page import Page
from app.pipeline.fetch_links import LinkedDocumentContent
from app.services import ingestion
from app.storage import objects


@pytest.fixture(autouse=True)
def _mock_friendly_s3(monkeypatch):
    monkeypatch.setattr(settings, "s3_endpoint_url", "")
    objects.get_s3_client.cache_clear()
    yield
    objects.get_s3_client.cache_clear()


class _FakeEmptyQuery:
    """No test in this file uses attachments (that's ingestion's supporting-document
    stage, not its linked-document stage) — this just returns an empty list.
    """

    def filter(self, *_conditions):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return []


class FakeSession:
    def __init__(self, document: Document) -> None:
        self._document = document
        self.added: list = []

    def get(self, model, pk):
        if model is Document and pk == self._document.id:
            return self._document
        return None

    def query(self, model):
        return _FakeEmptyQuery()

    def add(self, obj) -> None:
        if isinstance(obj, Page) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


def _cover_pdf_bytes(with_link: bool) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Cover sheet. See Annexure A for scope of work.")
    if with_link:
        page.insert_link(
            {
                "kind": fitz.LINK_URI,
                "uri": "https://bidplus.gem.gov.in/resources/biddoc/bid-1/x.pdf",
                "from": fitz.Rect(72, 72, 300, 90),
            }
        )
    data = doc.tobytes()
    doc.close()
    return data


def _linked_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_document(document_id: uuid.UUID, pdf_bytes: bytes) -> Document:
    objects.get_s3_client().create_bucket(Bucket=settings.s3_bucket)
    return Document(
        id=document_id,
        filename="GeM-Bidding-test.pdf",
        status="uploaded",
        original_pdf_s3_key=objects.upload_pdf(document_id, pdf_bytes),
    )


@mock_aws
def test_no_links_leaves_page_numbering_and_total_pages_unchanged() -> None:
    document_id = uuid.uuid4()
    document = _make_document(document_id, _cover_pdf_bytes(with_link=False))
    db = FakeSession(document)

    result = ingestion.run_ingestion(db, document_id)

    assert result.total_pages == 1
    page_rows = [row for row in db.added if isinstance(row, Page)]
    assert len(page_rows) == 1
    assert page_rows[0].source_url is None


@mock_aws
@patch("app.pipeline.fetch_links.get_cached_pages", return_value=None)
@patch("app.pipeline.fetch_links.store_cached_pages")
@patch("app.pipeline.fetch_links.resolve_linked_document")
def test_a_fetched_linked_pdf_appends_pages_continuing_the_number_sequence(
    mock_resolve, _mock_store, _mock_get_cached
) -> None:
    document_id = uuid.uuid4()
    document = _make_document(document_id, _cover_pdf_bytes(with_link=True))
    db = FakeSession(document)

    linked_bytes = _linked_pdf_bytes("Real eligibility criteria: turnover >= Rs 42 lakhs.")
    mock_resolve.return_value = LinkedDocumentContent(
        source_url="https://bidplus.gem.gov.in/resources/biddoc/bid-1/x.pdf",
        kind="pdf",
        pdf_bytes=linked_bytes,
    )

    result = ingestion.run_ingestion(db, document_id)

    # Critical gotcha from the plan: total_pages must reflect cover + linked pages, or
    # build_chunks (run later in the real pipeline chain) silently never reaches them.
    assert result.total_pages == 2

    page_rows = sorted(
        (row for row in db.added if isinstance(row, Page)), key=lambda p: p.page_number
    )
    assert [p.page_number for p in page_rows] == [0, 1]
    assert page_rows[0].source_url is None
    assert page_rows[1].source_url == "https://bidplus.gem.gov.in/resources/biddoc/bid-1/x.pdf"
    assert "turnover" in page_rows[1].raw_text


@mock_aws
@patch("app.pipeline.fetch_links.get_cached_pages")
@patch("app.pipeline.fetch_links.resolve_linked_document")
def test_a_cache_hit_never_calls_resolve_linked_document(
    mock_resolve, mock_get_cached
) -> None:
    from app.models.schemas import PageExtractionResult

    document_id = uuid.uuid4()
    document = _make_document(document_id, _cover_pdf_bytes(with_link=True))
    db = FakeSession(document)

    mock_get_cached.return_value = [
        PageExtractionResult(
            page_number=0, classification="native_text", extraction_method="native",
            raw_text="cached GTC text", content_hash="abc123", confidence_score=1.0,
        )
    ]

    result = ingestion.run_ingestion(db, document_id)

    mock_resolve.assert_not_called()
    assert result.total_pages == 2
    page_rows = sorted(
        (row for row in db.added if isinstance(row, Page)), key=lambda p: p.page_number
    )
    assert page_rows[1].raw_text == "cached GTC text"


@mock_aws
@patch("app.pipeline.fetch_links.get_cached_pages", return_value=None)
@patch("app.pipeline.fetch_links.resolve_linked_document", return_value=None)
def test_an_unreachable_link_is_skipped_not_fatal(_mock_resolve, _mock_get_cached) -> None:
    document_id = uuid.uuid4()
    document = _make_document(document_id, _cover_pdf_bytes(with_link=True))
    db = FakeSession(document)

    result = ingestion.run_ingestion(db, document_id)

    assert result.status == "extracted"
    assert result.total_pages == 1  # the cover page only — the link resolved to nothing
    page_rows = [row for row in db.added if isinstance(row, Page)]
    assert len(page_rows) == 1


@mock_aws
@patch("app.pipeline.fetch_links.get_cached_pages", return_value=None)
@patch("app.pipeline.fetch_links.resolve_linked_document")
def test_max_links_per_document_is_enforced(mock_resolve, _mock_get_cached, monkeypatch) -> None:
    monkeypatch.setattr(settings, "linked_doc_max_per_document", 0)

    document_id = uuid.uuid4()
    document = _make_document(document_id, _cover_pdf_bytes(with_link=True))
    db = FakeSession(document)

    result = ingestion.run_ingestion(db, document_id)

    mock_resolve.assert_not_called()
    assert result.total_pages == 1
