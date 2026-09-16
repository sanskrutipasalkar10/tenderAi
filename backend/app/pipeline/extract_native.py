"""Native text/table extraction — for pages classified native_text, table, or mixed
(docs/SPEC.md §2.1 stage 1). Free: no vision model call, PyMuPDF/pdfplumber only.

Two entry points:
  - extract_page_text: flat text for `pages.raw_text`, from the page's own text layer.
    Used for all three classifications above — even a table page gets flat text here
    (structured cells are separate, see below), matching the DDL's design: raw_text is
    "the extracted text, whatever the source."
  - extract_table_structure: structured rows/columns for `extracted_tables.table_data`,
    via pdfplumber's table-detection — kept separate from raw_text so BOQ/schedule rows
    aren't flattened into prose (spec §3.2).
"""

import hashlib
from io import BytesIO
from pathlib import Path

import fitz
import pdfplumber

from app.models.schemas import PageExtractionResult, TableCellData

MIN_TEXT_CHARS_FOR_HIGH_CONFIDENCE = 100


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def extract_page_text(page: fitz.Page) -> PageExtractionResult:
    """Extracts flat text from a native_text / table / mixed page.

    Always returns a result, even for a page with no extractable text (confidence 0.0)
    — CLAUDE.md's zero-page-drop invariant: a weak extraction is still a row, never a
    silently skipped one.
    """
    text = page.get_text()
    normalized = text.strip()

    if not normalized:
        return PageExtractionResult(
            page_number=page.number,
            classification="native_text",  # caller overrides with the real classification
            extraction_method="native",
            raw_text=None,
            content_hash=None,
            confidence_score=0.0,
        )

    confidence = 1.0 if len(normalized) >= MIN_TEXT_CHARS_FOR_HIGH_CONFIDENCE else 0.6
    return PageExtractionResult(
        page_number=page.number,
        classification="native_text",
        extraction_method="native",
        raw_text=normalized,
        content_hash=_content_hash(normalized),
        confidence_score=confidence,
    )


def extract_table_structure(
    pdf_source: Path | bytes, page_number: int
) -> TableCellData | None:
    """Structured table extraction for a single page, via pdfplumber's table-detection.

    Reopens the PDF via pdfplumber rather than reusing the caller's fitz handle — the
    two libraries don't share page objects, and table detection specifically needs
    pdfplumber's algorithm (fitz's own drawing data is used only for the cheaper
    classify.py grid heuristic, not full cell extraction).

    Accepts either a file path (eval/tests, reading fixtures off disk) or raw bytes (the
    ingestion worker, which fetches the PDF from S3 into memory — see
    app/services/ingestion.py).
    """
    source = BytesIO(pdf_source) if isinstance(pdf_source, bytes) else pdf_source
    with pdfplumber.open(source) as pdf:
        if page_number >= len(pdf.pages):
            return None
        plumber_page = pdf.pages[page_number]
        tables = plumber_page.extract_tables()

    if not tables:
        return None

    # First detected table on the page — a page with multiple distinct tables is an
    # edge case left for a later iteration (see docs/DECISIONS.md open items).
    raw_table = tables[0]
    if not raw_table:
        return None

    headers = [cell or "" for cell in raw_table[0]]
    rows = [[cell or "" for cell in row] for row in raw_table[1:]]
    return TableCellData(headers=headers, rows=rows)
