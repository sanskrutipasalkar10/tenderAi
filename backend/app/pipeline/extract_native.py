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
import re
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


_SERIAL_NUMBER_RE = re.compile(r"\d+\.?")


def _looks_like_data_row(row: list[str | None]) -> bool:
    """Tender BOQ/schedule tables' first column is almost always a serial number
    ('1', '19', '103') on data rows, and a text label ('Sl.No', 'Item No.') on the
    real header row. A page whose first "dense" row after preamble stripping starts
    with a bare number is a multi-page table's continuation page (the column-header
    row is only printed once, on the table's first page) — see docs/DECISIONS.md #26.
    """
    first_cell = (row[0] or "").strip()
    return bool(_SERIAL_NUMBER_RE.fullmatch(first_cell))


def _find_first_dense_row(raw_table: list[list[str | None]]) -> tuple[int, bool]:
    """Real tender tables routinely have title/preamble rows before the actual
    column-header row (a section name, an enquiry number — each with exactly one
    populated cell, the rest merged/empty; confirmed on a real BHEL tender document
    where 130/135 tables had this shape, see docs/DECISIONS.md #26). Returns the index
    of the first row where most columns are populated (i.e. the first row past any
    such preamble), and whether that row is a genuine header (True) or itself looks
    like a data row (False — see _looks_like_data_row), meaning this page is a
    continuation page of a multi-page table with no header row of its own.
    """
    if not raw_table:
        return 0, True
    num_cols = len(raw_table[0])
    threshold = max(2, num_cols // 2)
    for i, row in enumerate(raw_table):
        populated = sum(1 for cell in row if cell and cell.strip())
        if populated >= threshold:
            return i, not _looks_like_data_row(row)
    return 0, True  # no row looks dense — fall back to the first row as a header


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

    row_idx, is_header = _find_first_dense_row(raw_table)
    if is_header:
        headers = [cell or "" for cell in raw_table[row_idx]]
        rows = [[cell or "" for cell in row] for row in raw_table[row_idx + 1 :]]
    else:
        # Continuation page of a multi-page table — no header row printed here (see
        # _looks_like_data_row). Every row from here on is real data; nothing is
        # dropped, it's just correctly not mislabeled as a header.
        headers = []
        rows = [[cell or "" for cell in row] for row in raw_table[row_idx:]]
    return TableCellData(headers=headers, rows=rows)
