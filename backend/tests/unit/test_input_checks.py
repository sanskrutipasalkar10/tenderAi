"""Unit tests for app.guardrails.input_checks — real fitz PDF generation (small,
in-memory, no fixture files needed), no LLM/DB/network, per CLAUDE.md hard rule 8.
"""

import fitz
import pytest

from app.core.exceptions import DataQualityError
from app.guardrails.input_checks import looks_like_a_tender, validate_upload


def _pdf_with_text(text: str, pages: int = 1) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_looks_like_a_tender_true_for_real_tender_signal_terms() -> None:
    pdf_bytes = _pdf_with_text("NOTICE INVITING TENDER\nEMD: INR 50,000")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        assert looks_like_a_tender(doc) is True
    finally:
        doc.close()


def test_looks_like_a_tender_false_for_document_disclaiming_tender_status() -> None:
    # Real bug found via the golden adversarial fixture: a document that explicitly
    # says "It is not a tender, solicitation, or notice inviting bids of any kind"
    # contains the word "tender" (and "notice inviting") inside its own negation,
    # which a plain substring check would misread as a positive match.
    text = (
        "ANNUAL REPORT\nThis document summarizes company performance. "
        "It is not a tender, solicitation, or notice inviting bids of any kind."
    )
    doc = fitz.open(stream=_pdf_with_text(text), filetype="pdf")
    try:
        assert looks_like_a_tender(doc) is False
    finally:
        doc.close()


def test_looks_like_a_tender_false_for_unrelated_content() -> None:
    doc = fitz.open(stream=_pdf_with_text("Notes from Tuesday's lunch meeting"), filetype="pdf")
    try:
        assert looks_like_a_tender(doc) is False
    finally:
        doc.close()


def test_validate_upload_accepts_a_real_tender_pdf() -> None:
    validate_upload(_pdf_with_text("Request for Proposal — Bill of Quantities attached"))
    # no exception raised


def test_validate_upload_rejects_corrupt_bytes() -> None:
    with pytest.raises(DataQualityError):
        validate_upload(b"this is not a pdf at all")


def test_validate_upload_rejects_zero_page_pdf(monkeypatch) -> None:
    # fitz itself refuses to serialize a genuinely zero-page PDF (`ValueError: cannot
    # save with zero pages"), so there's no real byte string to construct one from —
    # fake fitz.open's return value instead, just for this one check.
    class _ZeroPageDoc:
        page_count = 0

        def close(self) -> None:
            pass

    import app.guardrails.input_checks as input_checks_module

    monkeypatch.setattr(input_checks_module.fitz, "open", lambda **_kw: _ZeroPageDoc())

    with pytest.raises(DataQualityError, match="no pages"):
        validate_upload(b"irrelevant, fitz.open is faked above")


def test_validate_upload_rejects_non_tender_content() -> None:
    with pytest.raises(DataQualityError, match="tender"):
        validate_upload(_pdf_with_text("Just a random memo about Tuesday's lunch order"))


def test_validate_upload_rejects_over_page_ceiling(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_pages", 2)
    over_ceiling_pdf = _pdf_with_text("NOTICE INVITING TENDER", pages=3)

    with pytest.raises(DataQualityError, match="exceeding"):
        validate_upload(over_ceiling_pdf)
