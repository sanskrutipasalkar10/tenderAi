"""Per-page classification — rule-based code, deliberately NOT an LLM call
(CLAUDE.md hard rule 3, docs/SPEC.md §10). This is the pipeline's first stage and the
subject of the Phase 2 gate measured "alone, before any LLM call" (docs/DECISIONS.md #4).

Signals used, all cheap and local to one page:
  - extractable text length (PyMuPDF's own text layer — zero for a true scan)
  - embedded raster images (a scan is rendered as one full-page image; a letterhead/
    stamp on an otherwise-native page is a smaller embedded image)
  - ruled-line grid structure (drawn table borders) via PyMuPDF's vector-drawing data

No OCR, no vision call happens here — a page classified "scanned_image" or "table" is a
routing decision for Phase 3's extraction step, not an extraction result itself.
"""

import fitz

MIN_TEXT_CHARS = 20
MIN_HORIZONTAL_LINES_FOR_TABLE = 3
MIN_VERTICAL_LINES_FOR_TABLE = 2
LINE_TOLERANCE = 1.0
MIN_LINE_LENGTH = 10.0


def _has_table_grid(page: fitz.Page) -> bool:
    """Detects a ruled table by counting distinct horizontal/vertical line segments
    among the page's vector drawings. Doesn't need pdfplumber — page.get_drawings()
    already exposes the line geometry PyMuPDF parsed from the page content stream.
    """
    horizontal = 0
    vertical = 0
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] != "l":  # only line segments
                continue
            p1, p2 = item[1], item[2]
            dx, dy = abs(p1.x - p2.x), abs(p1.y - p2.y)
            if dy < LINE_TOLERANCE and dx > MIN_LINE_LENGTH:
                horizontal += 1
            elif dx < LINE_TOLERANCE and dy > MIN_LINE_LENGTH:
                vertical += 1
    return horizontal >= MIN_HORIZONTAL_LINES_FOR_TABLE and vertical >= MIN_VERTICAL_LINES_FOR_TABLE


def classify_page(page: fitz.Page) -> str:
    """Returns one of PageClassification: native_text / scanned_image / table / mixed."""
    text = page.get_text().strip()
    has_significant_text = len(text) >= MIN_TEXT_CHARS
    has_images = len(page.get_images(full=True)) > 0
    has_table = has_significant_text and _has_table_grid(page)

    if has_table:
        return "table"
    if has_images and not has_significant_text:
        return "scanned_image"
    if has_images and has_significant_text:
        return "mixed"
    if has_significant_text:
        return "native_text"

    # Blank or unclassifiable page: conservative default. Routes to vision extraction
    # (Phase 3) rather than being silently trusted as empty native text — a page with
    # no signal at all is exactly the case a rule-based classifier should NOT guess on.
    return "scanned_image"


def classification_confidence(page: fitz.Page, classification: str) -> float:
    """A simple, explainable confidence score for the classification decision — not a
    model output, just how strong the signal was. Used to prioritize pages for human
    spot-checking (the citation-verification UI, docs/SPEC.md's HITL note) and to decide
    whether Phase 3's vision extraction should double-check a borderline case.
    """
    text_len = len(page.get_text().strip())
    if classification == "native_text":
        return 1.0 if text_len >= 200 else 0.7
    if classification == "scanned_image":
        return 1.0 if len(page.get_images(full=True)) > 0 and text_len == 0 else 0.5
    if classification == "table":
        return 0.9
    if classification == "mixed":
        return 0.8
    return 0.5
