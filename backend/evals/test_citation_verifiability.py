"""Phase 5 gate: citation verifiability — this project's real faithfulness metric,
replacing the Build Kit's generic RAG "faithfulness" eval (there is no retrieval step
here; see docs/DECISIONS.md row 4).

Directly operationalizes docs/SPEC.md §8's success criterion: "100% of
risk_finder.risks[].page_ref resolve to an existing pages row." Exercises the real
app.pipeline.citation_verify.verify_risk_citations function (no mocking needed here —
it's pure DB lookup logic, not an LLM call) against golden_risk_finder.jsonl's real
page numbers, using a fake Page-backed session per CLAUDE.md hard rule 8 (no real
Postgres needed for this check — a real-DB version of the same assertion runs in
tests/integration/ once that's wired against the live Postgres instance).
"""

import json
import uuid
from pathlib import Path

from app.models.page import Page
from app.pipeline import citation_verify

RISK_DATASET = Path(__file__).parent / "datasets" / "golden_risk_finder.jsonl"


class _FakePageQuery:
    def __init__(self, pages_by_number: dict[int, Page]) -> None:
        self._pages_by_number = pages_by_number
        self._page_number: int | None = None

    def filter(self, *conditions):
        for condition in conditions:
            right = getattr(condition, "right", None)
            if getattr(right, "value", None) is not None and isinstance(right.value, int):
                self._page_number = right.value
        return self

    def first(self):
        return self._pages_by_number.get(self._page_number)


class _FakeCitationSession:
    def __init__(self, pages_by_number: dict[int, Page]) -> None:
        self._pages_by_number = pages_by_number

    def query(self, model):
        if model is Page:
            return _FakePageQuery(self._pages_by_number)
        raise AssertionError(f"Unexpected query for {model}")


def load_risk_rows() -> list[dict]:
    return [json.loads(line) for line in RISK_DATASET.open(encoding="utf-8")]


def _make_page(document_id, page_number: int) -> Page:
    return Page(
        id=uuid.uuid4(),
        document_id=document_id,
        page_number=page_number,
        classification="native_text",
        raw_text="real page text",
        confidence_score=1.0,
    )


def test_every_golden_risk_page_ref_resolves_when_the_page_exists() -> None:
    """The realistic case: a document was fully extracted (every page has a `pages`
    row), so every risk's page_ref — however the reduce pass produced it — must
    verify.
    """
    document_id = uuid.uuid4()
    rows = load_risk_rows()
    page_numbers = {r["page_number"] for r in rows}
    db = _FakeCitationSession({n: _make_page(document_id, n) for n in page_numbers})

    risks = [
        {"category": r["expected_category"], "clause_summary": "...", "page_ref": r["page_number"]}
        for r in rows
    ]

    verified = citation_verify.verify_risk_citations(db, document_id, risks)

    assert all(r["verified"] for r in verified)
    assert len(verified) == len(risks)  # nothing dropped


def test_an_unresolvable_page_ref_is_marked_unverified_not_dropped() -> None:
    """docs/SPEC.md §7: an unverified fact/risk is shown as unverified, never hidden or
    guessed away — this is what protects the citation-verification UI's whole premise
    (every claim is clickable to a real page) from a hallucinated or off-by-one page_ref.
    """
    document_id = uuid.uuid4()
    db = _FakeCitationSession({1: _make_page(document_id, 1)})

    risks = [
        {"category": "Liquidated Damages", "clause_summary": "...", "page_ref": 1},
        {"category": "Indemnity", "clause_summary": "...", "page_ref": 9999},
    ]

    verified = citation_verify.verify_risk_citations(db, document_id, risks)

    assert verified[0]["verified"] is True
    assert verified[1]["verified"] is False
    assert len(verified) == 2
