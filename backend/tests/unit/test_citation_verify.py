"""Unit tests for app.pipeline.citation_verify — no real DB, per CLAUDE.md hard rule 8."""

import uuid

from app.models.page import Page
from app.pipeline import citation_verify


class FakePageQuery:
    """Captures the page_number equality filter well enough to answer `.first()`
    correctly for different page_refs within the same test — a real Page.filter(...)
    call, unlike most fakes in this test suite, needs to distinguish between multiple
    distinct page_ref lookups in one test rather than returning one fixed answer.
    """

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


class FakeCitationSession:
    def __init__(self, pages_by_number: dict[int, Page]) -> None:
        self._pages_by_number = pages_by_number

    def query(self, model):
        if model is Page:
            return FakePageQuery(self._pages_by_number)
        raise AssertionError(f"Unexpected query for {model}")


def _make_page(document_id, page_number) -> Page:
    return Page(
        id=uuid.uuid4(),
        document_id=document_id,
        page_number=page_number,
        classification="native_text",
        extraction_method="native",
        raw_text="some real page text",
        confidence_score=1.0,
    )


def test_page_ref_resolves_true_for_existing_page() -> None:
    document_id = uuid.uuid4()
    db = FakeCitationSession({3: _make_page(document_id, 3)})

    assert citation_verify.page_ref_resolves(db, document_id, 3) is True


def test_page_ref_resolves_false_for_missing_page() -> None:
    document_id = uuid.uuid4()
    db = FakeCitationSession({3: _make_page(document_id, 3)})

    assert citation_verify.page_ref_resolves(db, document_id, 99) is False


def test_verify_risk_citations_marks_each_risk_independently() -> None:
    document_id = uuid.uuid4()
    db = FakeCitationSession({1: _make_page(document_id, 1), 2: _make_page(document_id, 2)})
    risks = [
        {"category": "Liquidated Damages", "clause_summary": "...", "page_ref": 1},
        {"category": "Indemnity", "clause_summary": "...", "page_ref": 999},
    ]

    result = citation_verify.verify_risk_citations(db, document_id, risks)

    assert result[0]["verified"] is True
    assert result[1]["verified"] is False
    # Unresolvable citations are kept, marked unverified — never silently dropped
    # (docs/SPEC.md §7: shown as unverified, never hidden or guessed away).
    assert len(result) == 2
