from pathlib import Path

import fitz

from app.pipeline.extract_native import extract_page_text, extract_table_structure

FIXTURES_DIR = Path(__file__).parent.parent.parent / "evals" / "fixtures" / "pdfs"


def test_extract_native_text_page() -> None:
    doc = fitz.open(FIXTURES_DIR / "fixture_01_nhai_road.pdf")
    result = extract_page_text(doc[0])  # cover page, native_text
    doc.close()

    assert result.raw_text is not None
    assert "NOTICE INVITING TENDER" in result.raw_text
    assert result.content_hash is not None
    assert result.confidence_score > 0.0
    assert result.extraction_method == "native"


def test_extract_scanned_page_yields_no_text_not_a_crash() -> None:
    doc = fitz.open(FIXTURES_DIR / "fixture_01_nhai_road.pdf")
    result = extract_page_text(doc[5])  # scanned signature page
    doc.close()

    # extract_page_text is the NATIVE path — a scanned page correctly yields empty
    # text here (that's Phase 3's job), never a crash, never a missing result.
    assert result.raw_text is None
    assert result.confidence_score == 0.0


def test_content_hash_is_stable_for_identical_text() -> None:
    """The boilerplate dedupe fixture pair must hash identically on their shared pages
    (docs/DECISIONS.md's dedupe cache design) — this is the property Phase 3's
    boilerplate_cache lookup depends on.
    """
    doc_a = fitz.open(FIXTURES_DIR / "fixture_05_boilerplate_A.pdf")
    doc_b = fitz.open(FIXTURES_DIR / "fixture_06_boilerplate_B.pdf")

    result_a = extract_page_text(doc_a[1])  # shared GCC clause page
    result_b = extract_page_text(doc_b[1])
    doc_a.close()
    doc_b.close()

    assert result_a.content_hash == result_b.content_hash


def test_extract_table_structure_finds_boq_rows() -> None:
    table = extract_table_structure(FIXTURES_DIR / "fixture_01_nhai_road.pdf", 4)
    assert table is not None
    assert len(table.headers) == 6
    assert len(table.rows) == 5
    assert table.headers[0] == "Item No."


def test_extract_table_structure_returns_none_for_non_table_page() -> None:
    table = extract_table_structure(FIXTURES_DIR / "fixture_01_nhai_road.pdf", 0)
    assert table is None
