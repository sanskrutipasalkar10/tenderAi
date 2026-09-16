"""Unit tests for app.pipeline.reduce_pass — LLM call mocked at complete_structured, no
real DB, per CLAUDE.md hard rule 8. Golden-set-derived accuracy (does risk_finder find
the right category/severity, does go_no_go match the golden decision) belongs in
evals/test_reduce_*.py once those are wired against this real architecture.
"""

import uuid

from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.page import Page
from app.models.schemas import (
    GoNoGoCriterionMatch,
    GoNoGoLLMResult,
    MapPassAmountFact,
    MapPassCriterionFact,
    MapPassDateFact,
    MapPassResult,
    MapPassRiskCandidate,
    RiskFinderLLMResult,
    RiskFinderLLMRisk,
    SynopsisLLMResult,
)
from app.pipeline import reduce_pass

QUALIFIED_PROFILE = {
    "company_name": "Test Infra Builders",
    "annual_turnover": {"2024": 720000000.0},
    "certifications": ["ISO 9001:2015"],
    "past_projects": [],
    "geographic_presence": ["Maharashtra"],
    "sectors": ["road construction"],
    "max_capacity_pct": 60,
}

INCOMPLETE_PROFILE = {
    "company_name": "Test Infra Builders",
    "annual_turnover": {"2024": 720000000.0},
    "certifications": None,
    "past_projects": [],
    "geographic_presence": ["Maharashtra"],
    "sectors": None,
    "max_capacity_pct": 60,
}


class _FakeListQuery:
    def __init__(self, items: list) -> None:
        self._items = items

    def filter(self, *_conditions):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _FakePageQuery:
    """See tests/unit/test_citation_verify.py's twin of this class for why a smarter,
    filter-inspecting fake is needed here specifically (multiple distinct page_ref
    lookups within one test), unlike the simpler pre-filtered fakes used elsewhere.
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


class FakeReduceSession:
    def __init__(
        self,
        chunk_extractions: list[ChunkExtraction] | None = None,
        pages_by_number: dict[int, Page] | None = None,
        existing_analysis: DocumentAnalysis | None = None,
    ) -> None:
        self._chunks = [
            Chunk(id=e.chunk_id, document_id=uuid.uuid4()) for e in chunk_extractions or []
        ]
        self._chunk_extractions = chunk_extractions or []
        self._pages_by_number = pages_by_number or {}
        self._existing_analysis = existing_analysis
        self.added: list = []

    def query(self, model):
        if model is Chunk:
            return _FakeListQuery(self._chunks)
        if model is ChunkExtraction:
            return _FakeListQuery(self._chunk_extractions)
        if model is Page:
            return _FakePageQuery(self._pages_by_number)
        if model is DocumentAnalysis:
            return _FakeListQuery([self._existing_analysis] if self._existing_analysis else [])
        raise AssertionError(f"Unexpected query for {model}")

    def add(self, obj) -> None:
        if isinstance(obj, DocumentAnalysis) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


def _extraction(structured_json: dict) -> ChunkExtraction:
    return ChunkExtraction(
        id=uuid.uuid4(), chunk_id=uuid.uuid4(), structured_json=structured_json, model_used="test"
    )


def _document() -> Document:
    return Document(id=uuid.uuid4(), filename="x.pdf", status="analyzing", total_pages=5)


# --- go_no_go ------------------------------------------------------------------------


def test_go_no_go_incomplete_profile_skips_llm_and_returns_conditional_go(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(
        chunk_extractions=[_extraction(MapPassResult(criteria=[
            MapPassCriterionFact(description="Min turnover 50 Cr", page_ref=1)
        ]).model_dump())]
    )

    def _should_not_be_called(*_args, **_kwargs):
        raise AssertionError("complete_structured must not be called for an incomplete profile")

    monkeypatch.setattr(reduce_pass, "complete_structured", _should_not_be_called)

    analysis = reduce_pass.run_go_no_go(db, document, INCOMPLETE_PROFILE)

    assert analysis.result["decision"] == "Conditional-Go"
    assert set(analysis.result["gaps"]) == {"certifications", "sectors"}
    assert analysis.model_used is None


def test_go_no_go_no_criteria_found_skips_llm(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(chunk_extractions=[_extraction(MapPassResult().model_dump())])

    monkeypatch.setattr(
        reduce_pass,
        "complete_structured",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call LLM")),
    )

    analysis = reduce_pass.run_go_no_go(db, document, QUALIFIED_PROFILE)

    assert analysis.result["decision"] == "Conditional-Go"
    assert "No eligibility criteria found" in analysis.result["gaps"][0]


def test_go_no_go_all_pass_yields_go_decision(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(
        chunk_extractions=[
            _extraction(
                MapPassResult(
                    criteria=[MapPassCriterionFact(description="Min turnover 50 Cr", page_ref=1)]
                ).model_dump()
            )
        ]
    )
    fake_llm_result = GoNoGoLLMResult(
        criteria_matches=[
            GoNoGoCriterionMatch(
                criterion="Min turnover 50 Cr",
                required="INR 50 Cr",
                company_value="INR 72 Cr",
                status="pass",
                page_ref=1,
            )
        ],
        next_steps=["Prepare EMD"],
    )
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda *a, **k: (fake_llm_result, "test-model")
    )

    analysis = reduce_pass.run_go_no_go(db, document, QUALIFIED_PROFILE)

    assert analysis.result["decision"] == "Go"
    assert analysis.result["score"] == 100
    assert analysis.result["gaps"] == []
    assert analysis in db.added


def test_go_no_go_any_fail_yields_no_go_decision(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(
        chunk_extractions=[
            _extraction(
                MapPassResult(
                    criteria=[MapPassCriterionFact(description="Min turnover 250 Cr", page_ref=1)]
                ).model_dump()
            )
        ]
    )
    fake_llm_result = GoNoGoLLMResult(
        criteria_matches=[
            GoNoGoCriterionMatch(
                criterion="Min turnover 250 Cr",
                required="INR 250 Cr",
                company_value="INR 72 Cr",
                status="fail",
                page_ref=1,
            )
        ]
    )
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda *a, **k: (fake_llm_result, "test-model")
    )

    analysis = reduce_pass.run_go_no_go(db, document, QUALIFIED_PROFILE)

    assert analysis.result["decision"] == "No-Go"
    assert analysis.result["score"] == 0


# --- risk_finder ---------------------------------------------------------------------


def test_risk_finder_no_candidates_skips_llm(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(chunk_extractions=[_extraction(MapPassResult().model_dump())])
    monkeypatch.setattr(
        reduce_pass,
        "complete_structured",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call LLM")),
    )

    analysis = reduce_pass.run_risk_finder(db, document)

    assert analysis.result == {"risk_score": 0, "risks": []}


def test_risk_finder_assigns_severity_by_rubric_not_llm(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(
        chunk_extractions=[
            _extraction(
                MapPassResult(
                    risk_candidates=[
                        MapPassRiskCandidate(
                            category="Liquidated Damages", clause_summary="1%/week", page_ref=4
                        )
                    ]
                ).model_dump()
            )
        ],
        pages_by_number={4: Page(id=uuid.uuid4(), document_id=document.id, page_number=4,
                                  classification="native_text", raw_text="LD clause text",
                                  confidence_score=1.0)},
    )
    fake_llm_result = RiskFinderLLMResult(
        risks=[
            RiskFinderLLMRisk(category="Liquidated Damages", clause_summary="1%/week", page_ref=4)
        ]
    )
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda *a, **k: (fake_llm_result, "test-model")
    )

    analysis = reduce_pass.run_risk_finder(db, document)

    risk = analysis.result["risks"][0]
    assert risk["severity"] == "HIGH"  # from SEVERITY_BY_CATEGORY, not the mocked LLM response
    assert risk["verified"] is True
    assert analysis.result["risk_score"] == 30  # _SEVERITY_WEIGHT["HIGH"]


def test_risk_finder_unrecognized_category_gets_default_severity(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(
        chunk_extractions=[
            _extraction(
                MapPassResult(
                    risk_candidates=[
                        MapPassRiskCandidate(
                            category="Some Novel Clause Type", clause_summary="...", page_ref=2
                        )
                    ]
                ).model_dump()
            )
        ],
        pages_by_number={},  # page_ref 2 does not resolve
    )
    fake_llm_result = RiskFinderLLMResult(
        risks=[
            RiskFinderLLMRisk(
                category="Some Novel Clause Type", clause_summary="...", page_ref=2
            )
        ]
    )
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda *a, **k: (fake_llm_result, "test-model")
    )

    analysis = reduce_pass.run_risk_finder(db, document)

    risk = analysis.result["risks"][0]
    assert risk["severity"] == reduce_pass.DEFAULT_SEVERITY
    assert risk["verified"] is False  # shown unverified, never dropped (docs/SPEC.md §7)


# --- synopsis --------------------------------------------------------------------


def test_synopsis_no_facts_skips_llm_and_returns_low_confidence(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(chunk_extractions=[_extraction(MapPassResult().model_dump())])
    monkeypatch.setattr(
        reduce_pass,
        "complete_structured",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call LLM")),
    )

    analysis = reduce_pass.run_synopsis(db, document)

    assert analysis.result["confidence"] == "low"
    assert analysis.result["key_dates"] == []


def test_synopsis_key_dates_pass_through_from_map_pass_not_llm(monkeypatch) -> None:
    document = _document()
    db = FakeReduceSession(
        chunk_extractions=[
            _extraction(
                MapPassResult(
                    dates=[MapPassDateFact(label="Bid deadline", value="15 Nov 2026", page_ref=2)],
                    amounts=[MapPassAmountFact(label="EMD", value="INR 50 Lakh", page_ref=3)],
                ).model_dump()
            )
        ]
    )
    fake_llm_result = SynopsisLLMResult(
        title="Test Tender",
        issuing_authority="Test Authority",
        scope_summary="...",
        eligibility_summary="...",
        payment_terms_summary="...",
        confidence="high",
    )
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda *a, **k: (fake_llm_result, "test-model")
    )

    analysis = reduce_pass.run_synopsis(db, document)

    assert analysis.result["key_dates"] == [
        {"label": "Bid deadline", "value": "15 Nov 2026", "page_ref": 2}
    ]
    assert analysis.result["financials"] == [
        {"label": "EMD", "value": "INR 50 Lakh", "page_ref": 3}
    ]
    assert analysis.result["title"] == "Test Tender"


def test_synopsis_dedupes_exact_duplicate_dates_from_overlapping_chunks(monkeypatch) -> None:
    document = _document()
    duplicate_date = MapPassDateFact(label="Bid deadline", value="15 Nov 2026", page_ref=2)
    db = FakeReduceSession(
        chunk_extractions=[
            _extraction(MapPassResult(dates=[duplicate_date]).model_dump()),
            _extraction(MapPassResult(dates=[duplicate_date]).model_dump()),
        ]
    )
    fake_llm_result = SynopsisLLMResult(
        title="T", issuing_authority="A", scope_summary="s",
        eligibility_summary="e", payment_terms_summary="p", confidence="high",
    )
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda *a, **k: (fake_llm_result, "test-model")
    )

    analysis = reduce_pass.run_synopsis(db, document)

    assert len(analysis.result["key_dates"]) == 1


# --- upsert ----------------------------------------------------------------------


def test_rerunning_a_module_upserts_the_existing_row_not_a_duplicate(monkeypatch) -> None:
    document = _document()
    existing = DocumentAnalysis(
        id=uuid.uuid4(),
        document_id=document.id,
        module="risk_finder",
        result={"risk_score": 0, "risks": []},
        model_used=None,
    )
    db = FakeReduceSession(
        chunk_extractions=[_extraction(MapPassResult().model_dump())], existing_analysis=existing
    )

    analysis = reduce_pass.run_risk_finder(db, document)

    assert analysis is existing  # same row updated, not a new insert
    assert db.added == []  # nothing new was db.add()-ed
