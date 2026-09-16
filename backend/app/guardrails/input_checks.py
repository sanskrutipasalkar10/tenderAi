"""Upload-time guardrails — cheap, deterministic heuristics (no LLM call) that run
before the expensive pipeline does. docs/SPEC.md §11: an uploaded document that isn't
actually a tender should be flagged, never confidently analyzed as if it were one.
Also the home of the other upload-time rejections spec §5 calls for (corrupt/0-page
PDF, over the page ceiling) — same "cheap deterministic check before the real pipeline
runs" rationale, so they live together rather than scattered across routes_ingest.py.
"""

import fitz

from app.core.config import settings
from app.core.exceptions import DataQualityError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Terms that show up in essentially every genuine Indian government tender's opening
# pages — a notice inviting tender, an RFP cover, or a BOQ header will contain at least
# one of these. Deliberately permissive (a false "yes" just proceeds to the real
# pipeline; a false "no" would wrongly block a real tender) — this is a cheap first
# filter, not a classifier to be trusted alone.
TENDER_SIGNAL_TERMS = (
    "tender",
    "notice inviting",
    "nit no",
    "rfp",
    "request for proposal",
    "earnest money deposit",
    "emd",
    "bill of quantities",
    "boq",
    "eligibility criteria",
    "bid submission",
    "tender no",
)

PAGES_TO_CHECK = 3

# A real non-tender document (an annual report, in the golden adversarial fixture)
# explicitly disclaiming tender status — "It is not a tender, solicitation, or notice
# inviting bids of any kind" — defeats a plain substring check on TENDER_SIGNAL_TERMS,
# since "tender" and "notice inviting" both appear verbatim inside the negation itself.
# Checked first and short-circuits to False: an explicit "this is NOT a tender"
# disclaimer is a far stronger, more specific signal than the presence of the bare
# word (docs/DECISIONS.md #46).
NEGATION_PHRASES = (
    "not a tender",
    "not a solicitation",
    "not a notice inviting",
    "is not a tender",
)


def looks_like_a_tender(doc: fitz.Document) -> bool:
    """Cheap heuristic on the first few pages — a real tender's cover/notice/BOQ
    section almost always contains at least one of TENDER_SIGNAL_TERMS. Takes an
    already-open fitz.Document (not a path) so validate_upload can open the PDF once
    and reuse it for every check below, rather than each check re-opening the file.
    """
    text = ""
    for i in range(min(PAGES_TO_CHECK, doc.page_count)):
        text += doc[i].get_text().lower()
    if any(phrase in text for phrase in NEGATION_PHRASES):
        return False
    return any(term in text for term in TENDER_SIGNAL_TERMS)


def validate_upload(pdf_bytes: bytes) -> None:
    """Raises DataQualityError for anything that must never reach the pipeline: a
    corrupt/unreadable file, zero pages, over the page ceiling (docs/SPEC.md §5), or
    content that doesn't look like a tender at all (§11's out-of-domain "refuse/flag,
    never silently proceed" rule). Every rejection is logged — a rejected upload is
    real signal, either a bad file or the heuristic itself needing a tune.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.warning("input_checks.upload_rejected", reason="corrupt_or_unreadable_pdf")
        raise DataQualityError("Uploaded file could not be opened as a PDF") from exc

    try:
        if doc.page_count == 0:
            logger.warning("input_checks.upload_rejected", reason="zero_pages")
            raise DataQualityError("Uploaded PDF has no pages")

        if doc.page_count > settings.max_upload_pages:
            logger.warning(
                "input_checks.upload_rejected",
                reason="over_page_ceiling",
                page_count=doc.page_count,
                ceiling=settings.max_upload_pages,
            )
            raise DataQualityError(
                f"PDF has {doc.page_count} pages, exceeding the "
                f"{settings.max_upload_pages}-page upload limit"
            )

        if not looks_like_a_tender(doc):
            logger.warning("input_checks.upload_rejected", reason="does_not_look_like_a_tender")
            raise DataQualityError(
                "This document does not appear to be a tender document"
            )
    finally:
        doc.close()
