"""_run_pq_checklist / PQ_CHECKLIST_CATEGORIES — pure code + a mocked LLM call, no DB
(docs/DECISIONS.md). Informational only: never feeds check_hard_gates/
compute_weighted_score/decide, and a failure here must never block the main go_no_go
decision (same resilience principle as docs/DECISIONS.md #62).
"""

import uuid

from app.core.exceptions import ProviderError
from app.models.schemas import (
    MapPassAmountFact,
    MapPassCriterionFact,
    MapPassDateFact,
    MapPassResult,
    PQChecklistItem,
    PQChecklistLLMResult,
)
from app.pipeline import reduce_pass


def test_pq_checklist_categories_has_exactly_28_entries() -> None:
    """Golden-constant guard — Section A of the real framework spreadsheet has
    exactly 28 rows; an accidental edit here should fail loudly.
    """
    assert len(reduce_pass.PQ_CHECKLIST_CATEGORIES) == 28
    assert len(set(reduce_pass.PQ_CHECKLIST_CATEGORIES)) == 28  # no duplicates


def test_format_facts_content_includes_dates_amounts_and_criteria() -> None:
    facts = MapPassResult(
        dates=[MapPassDateFact(label="Bid deadline", value="15 Nov 2026", page_ref=1)],
        amounts=[MapPassAmountFact(label="EMD", value="INR 50 Lakh", page_ref=2)],
        criteria=[MapPassCriterionFact(description="Min turnover 50 Cr", page_ref=3)],
    )

    content = reduce_pass._format_facts_content(facts)

    assert "Bid deadline: 15 Nov 2026" in content
    assert "EMD: INR 50 Lakh" in content
    assert "Min turnover 50 Cr" in content
    assert "[PAGE 1]" in content
    assert "[PAGE 2]" in content
    assert "[PAGE 3]" in content


def _full_checklist_result() -> PQChecklistLLMResult:
    return PQChecklistLLMResult(
        items=[
            PQChecklistItem(category=c, status="not_applicable")
            for c in reduce_pass.PQ_CHECKLIST_CATEGORIES
        ]
    )


def test_run_pq_checklist_returns_none_on_provider_error(monkeypatch) -> None:
    """A failure in this secondary, informational call must degrade gracefully, not
    raise and block the main go_no_go decision.
    """

    def _raise(task, prompt, schema):
        raise ProviderError("cloud and local both unavailable")

    monkeypatch.setattr(reduce_pass, "complete_structured", _raise)

    result = reduce_pass._run_pq_checklist(MapPassResult(), {}, uuid.uuid4())

    assert result is None


def test_run_pq_checklist_returns_full_list_on_success(monkeypatch) -> None:
    fake_result = _full_checklist_result()
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda task, prompt, schema: (fake_result, "test-model")
    )

    result = reduce_pass._run_pq_checklist(MapPassResult(), {}, uuid.uuid4())

    assert result is not None
    assert len(result) == 28
    assert {item.category for item in result} == set(reduce_pass.PQ_CHECKLIST_CATEGORIES)


def test_run_pq_checklist_returns_partial_items_on_category_mismatch(monkeypatch) -> None:
    """A model that omits or invents a category logs a warning (not tested here — no
    existing precedent for asserting log content in this codebase) but still returns
    whatever it did produce — partial is more useful than nothing.
    """
    partial_result = PQChecklistLLMResult(
        items=[
            PQChecklistItem(category=reduce_pass.PQ_CHECKLIST_CATEGORIES[0], status="pass"),
            PQChecklistItem(category=reduce_pass.PQ_CHECKLIST_CATEGORIES[1], status="fail"),
        ]
    )
    monkeypatch.setattr(
        reduce_pass,
        "complete_structured",
        lambda task, prompt, schema: (partial_result, "test-model"),
    )

    result = reduce_pass._run_pq_checklist(MapPassResult(), {}, uuid.uuid4())

    assert result is not None
    assert len(result) == 2
