from pathlib import Path

import fitz
import pytest

from app.pipeline.classify import classification_confidence, classify_page

FIXTURES_DIR = Path(__file__).parent.parent.parent / "evals" / "fixtures" / "pdfs"


@pytest.mark.parametrize(
    ("fixture", "page_number", "expected"),
    [
        ("fixture_01_nhai_road", 0, "native_text"),
        ("fixture_01_nhai_road", 4, "table"),
        ("fixture_01_nhai_road", 5, "scanned_image"),
        ("fixture_02_pwd_building", 0, "mixed"),
        ("fixture_04_railway_scanned", 0, "scanned_image"),
    ],
)
def test_classify_page_matches_known_fixture_pages(
    fixture: str, page_number: int, expected: str
) -> None:
    doc = fitz.open(FIXTURES_DIR / f"{fixture}.pdf")
    result = classify_page(doc[page_number])
    doc.close()
    assert result == expected


def test_confidence_is_bounded() -> None:
    doc = fitz.open(FIXTURES_DIR / "fixture_01_nhai_road.pdf")
    for page in doc:
        classification = classify_page(page)
        confidence = classification_confidence(page, classification)
        assert 0.0 <= confidence <= 1.0
    doc.close()


def test_blank_page_defaults_to_scanned_image_not_a_guess() -> None:
    doc = fitz.open()
    doc.new_page()
    result = classify_page(doc[0])
    doc.close()
    assert result == "scanned_image"
