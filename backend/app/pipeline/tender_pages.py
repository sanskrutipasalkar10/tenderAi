"""Loads a tender's own page text for the reduce-pass checks that read pages directly
(the About Project brief, the consortium-policy check) rather than map-pass facts.

Drops GeM's General Terms and Conditions — the same ~57 pages linked from every GeM
bid. They say nothing specific to this tender, and their generic clauses ("Scope of
Contract", consortium wording) would otherwise be mistaken for this tender's own
(docs/DECISIONS.md #92).
"""

import re

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.page import Page

_STANDARD_TERMS_URL = re.compile(r"/gtc/", re.IGNORECASE)
_STANDARD_TERMS_TEXT = re.compile(r"General\s+Terms\s+and\s+Conditions\s+on\s+GeM", re.IGNORECASE)


def is_standard_terms_page(text: str, source_url: str | None = None) -> bool:
    if source_url and _STANDARD_TERMS_URL.search(source_url):
        return True
    return bool(_STANDARD_TERMS_TEXT.search(text))


def load_tender_pages(db: Session, document: Document) -> list[tuple[int, str]]:
    """(page_number, raw_text) for every page with text, in page order, minus GeM's
    standard terms pages."""
    rows = (
        db.query(Page.page_number, Page.raw_text, Page.source_url)
        .filter(Page.document_id == document.id, Page.raw_text.isnot(None))
        .order_by(Page.page_number)
        .all()
    )
    return [
        (row.page_number, row.raw_text)
        for row in rows
        if row.raw_text.strip() and not is_standard_terms_page(row.raw_text, row.source_url)
    ]
