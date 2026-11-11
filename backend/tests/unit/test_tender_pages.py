"""Unit tests for app.pipeline.tender_pages."""

import uuid

from app.models.document import Document
from app.pipeline.tender_pages import is_standard_terms_page, load_tender_pages


def _document() -> Document:
    return Document(id=uuid.uuid4(), filename="x.pdf", status="analyzing")


def test_drops_pages_fetched_from_the_gem_terms_link() -> None:
    class _Row:
        def __init__(self, number: int, url: str | None) -> None:
            self.page_number, self.raw_text, self.source_url = number, f"page {number}", url

    class _Query:
        def filter(self, *_):
            return self

        def order_by(self, *_):
            return self

        def all(self):
            return [
                _Row(0, None),
                _Row(1, "https://gem.gov.in/documentdownload/10005697/1791458046.pdf"),
                _Row(2, "https://assets-bg.gem.gov.in/apis/v1/gtc/pdfByDate/?date=20261008"),
            ]

    class _Session:
        def query(self, *_):
            return _Query()

    assert [n for n, _ in load_tender_pages(_Session(), _document())] == [0, 1]


def test_recognises_gem_terms_by_their_header_text() -> None:
    assert is_standard_terms_page("General Terms and Conditions on GeM 4.0 (Version 1.29)")
    assert not is_standard_terms_page("Bid Details\nEMD Amount 100000")
