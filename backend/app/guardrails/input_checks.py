"""Upload-time guardrails — cheap, deterministic heuristics (no LLM call) that run
before the expensive pipeline does. docs/SPEC.md §11: an uploaded document that isn't
actually a tender should be flagged, never confidently analyzed as if it were one.
"""

from pathlib import Path

import fitz

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


def looks_like_a_tender(pdf_path: Path) -> bool:
    """Cheap heuristic on the first few pages — a real tender's cover/notice/BOQ
    section almost always contains at least one of TENDER_SIGNAL_TERMS.
    """
    doc = fitz.open(pdf_path)
    text = ""
    for i in range(min(PAGES_TO_CHECK, doc.page_count)):
        text += doc[i].get_text().lower()
    doc.close()
    return any(term in text for term in TENDER_SIGNAL_TERMS)
