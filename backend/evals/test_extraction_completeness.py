"""Phase 2/3 gate: the zero-page-drop invariant, plus vision-extraction field accuracy.

Zero-page-drop is a hard, non-negotiable invariant (docs/SPEC.md §8): for every
processed document, COUNT(pages) == documents.total_pages. A failed extraction still
writes a `pages` row (low confidence_score, possibly null raw_text) — it never produces
a missing row. This is checked directly against the fixtures here, independent of the DB
layer, so it's testable before Phase 2's storage code exists too.

Expected to fail with ImportError until Phase 2/3 build the ingestion pipeline.
"""

from pathlib import Path

import fitz
import pytest

from app.pipeline.classify import classify_page  # noqa: F401
from app.pipeline.extract_native import extract_page_text  # noqa: F401
from app.pipeline.extract_vision import extract_page_via_vision  # noqa: F401

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"


def all_fixture_paths() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.pdf"))


@pytest.mark.parametrize("fixture_path", all_fixture_paths(), ids=lambda p: p.stem)
def test_zero_pages_dropped(fixture_path: Path) -> None:
    doc = fitz.open(fixture_path)
    total_pages = doc.page_count

    processed_pages = 0
    for page in doc:
        classification = classify_page(page)
        if classification in ("native_text", "table", "mixed"):
            result = extract_page_text(page)
        else:
            result = extract_page_via_vision(page)
        # A page is "processed" if extraction produced a row at all — even a low
        # confidence / partial one. It must never be silently skipped.
        assert result is not None, (
            f"{fixture_path.stem} page {page.number}: extraction produced no row at all "
            f"(silently dropped) — this must never happen regardless of extraction quality"
        )
        processed_pages += 1
    doc.close()

    assert processed_pages == total_pages, (
        f"{fixture_path.stem}: {total_pages} pages in PDF but only "
        f"{processed_pages} produced a pages row"
    )


def test_vision_extraction_on_golden_scanned_pages() -> None:
    """Field-level accuracy on scanned/table pages, tuned once Phase 3 exists.

    Placeholder target (docs/SPEC.md §8): >=90%. Real assertions land in Phase 3 once
    extract_vision.py exists and there's a defined "field" shape to score against
    (currently golden_pages.jsonl only carries a classification label, not per-field
    ground truth for scanned content — that's an open item for Phase 3, see
    docs/DECISIONS.md's open-decisions list).
    """
    pytest.skip("Vision extraction not implemented until Phase 3")
