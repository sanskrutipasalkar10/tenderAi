"""rescore_go_no_go / _format_reviewed_criteria_content — the "Resubmit analysis"
action (docs/DECISIONS.md): re-asks the model for fresh factor_scores against an
already-reviewed go_no_go analysis's criteria_matches, so score/decision actually move
to reflect a bid team's review. LLM/DB mocked per CLAUDE.md hard rule 8.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import DataQualityError, ProviderError
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.schemas import GoNoGoCriterionMatch, GoNoGoRescoreLLMResult
from app.pipeline import reduce_pass

_ALL_HIGH = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 90)
_ALL_LOW = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 0)


def _analysis(result: dict, document_id: uuid.UUID) -> DocumentAnalysis:
    return DocumentAnalysis(
        id=uuid.uuid4(),
        document_id=document_id,
        module="go_no_go",
        result=result,
        model_used="ollama_chat/gpt-oss:120b-cloud",
        created_at=datetime.now(timezone.utc),
    )


def _base_result(**overrides) -> dict:
    base = {
        "score": 0,
        "decision": "No-Go",
        "criteria_matches": [
            {
                "criterion": "Mandatory ISO 9001 certification",
                "required": "ISO 9001:2015",
                "company_value": "No relevant information in company profile",
                "status": "insufficient_data",
                "page_ref": 2,
                "gate": "Mandatory certification unavailable",
                "criterion_type": "eligibility",
                "human_override": {
                    "status": "pass",
                    "note": "Certificate on file, verified 2026-09-23",
                    "original_status": "insufficient_data",
                    "reviewed_at": "2026-09-23T10:00:00+00:00",
                },
            },
            {
                "criterion": "Self-attested English translation",
                "required": "Required for non-English docs",
                "company_value": "No specific company data required",
                "status": "pass",
                "page_ref": 3,
                "gate": None,
                "criterion_type": "procedural",
                "human_override": None,
            },
        ],
        "gaps": [],
        "next_steps": [],
        "factor_scores": dict(_ALL_LOW),
        "pq_checklist": None,
        "documents_required": [],
        "tq_score": None,
        "tq_factor_scores": None,
        "commercial_competitiveness": None,
        "bid_preparation_effort": None,
        "major_qualification_gap": None,
        "major_technical_gap": None,
    }
    base.update(overrides)
    return base


class _FakeSession:
    def __init__(self, analysis: DocumentAnalysis | None) -> None:
        self._analysis = analysis
        self.commit = MagicMock()
        self.refresh = MagicMock()

    def query(self, model):
        assert model is DocumentAnalysis
        return self

    def filter(self, *_conditions):
        return self

    def first(self):
        return self._analysis


def test_format_reviewed_criteria_content_tags_human_reviewed_and_skips_procedural() -> None:
    matches = [
        GoNoGoCriterionMatch.model_validate(m) for m in _base_result()["criteria_matches"]
    ]

    content = reduce_pass._format_reviewed_criteria_content(matches)

    assert "human-reviewed" in content
    assert "Certificate on file, verified 2026-09-23" in content
    assert "-> pass" in content  # effective status, not the original insufficient_data
    assert "Self-attested English translation" not in content  # procedural, excluded


def test_format_reviewed_criteria_content_no_tag_for_unreviewed_criterion() -> None:
    match = GoNoGoCriterionMatch(
        criterion="Minimum turnover INR 5 Cr", required="INR 5 Cr", company_value="INR 2 Cr",
        status="fail", page_ref=4, gate="Turnover not met and no valid exemption",
        criterion_type="eligibility", human_override=None,
    )

    content = reduce_pass._format_reviewed_criteria_content([match])

    assert "human-reviewed" not in content
    assert "-> fail" in content


def test_rescore_raises_data_quality_error_when_no_analysis_exists() -> None:
    db = _FakeSession(None)
    document = Document(id=uuid.uuid4(), filename="t.pdf", status="ready")

    with pytest.raises(DataQualityError, match="No go_no_go analysis"):
        reduce_pass.rescore_go_no_go(db, document, {})


def test_rescore_raises_data_quality_error_when_short_circuited_with_no_factor_scores() -> None:
    document_id = uuid.uuid4()
    analysis = _analysis(_base_result(factor_scores=None), document_id)
    db = _FakeSession(analysis)
    document = Document(id=document_id, filename="t.pdf", status="ready")

    with pytest.raises(DataQualityError, match="no factor_scores to rescore"):
        reduce_pass.rescore_go_no_go(db, document, {})


def test_rescore_recomputes_score_and_decision_from_fresh_factor_scores(monkeypatch) -> None:
    document_id = uuid.uuid4()
    analysis = _analysis(_base_result(), document_id)
    db = _FakeSession(analysis)
    document = Document(id=document_id, filename="t.pdf", status="ready")

    fresh = GoNoGoRescoreLLMResult(factor_scores=dict(_ALL_HIGH))
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda task, prompt, schema: (fresh, "test-model")
    )

    updated = reduce_pass.rescore_go_no_go(db, document, {"company_name": "Acme"})

    assert updated.result["factor_scores"] == _ALL_HIGH
    assert updated.result["score"] == 90
    # No gate is triggered any more (the only gate-tagged criterion was overridden to
    # pass), so the all-90s factor score bands to a clean "Go."
    assert updated.result["decision"] == "Go"
    assert updated.result["gaps"] == []
    db.commit.assert_called_once()


def test_rescore_keeps_the_gate_triggered_if_a_gated_criterion_is_still_failing(
    monkeypatch,
) -> None:
    document_id = uuid.uuid4()
    result = _base_result(
        criteria_matches=[
            {
                "criterion": "Minimum turnover INR 5 Cr", "required": "INR 5 Cr",
                "company_value": "INR 2 Cr", "status": "fail", "page_ref": 4,
                "gate": "Turnover not met and no valid exemption",
                "criterion_type": "eligibility", "human_override": None,
            }
        ],
    )
    analysis = _analysis(result, document_id)
    db = _FakeSession(analysis)
    document = Document(id=document_id, filename="t.pdf", status="ready")

    fresh = GoNoGoRescoreLLMResult(factor_scores=dict(_ALL_HIGH))
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda task, prompt, schema: (fresh, "test-model")
    )

    updated = reduce_pass.rescore_go_no_go(db, document, {})

    assert updated.result["decision"] == "No-Go"
    assert updated.result["gaps"] == ["Turnover not met and no valid exemption"]


def test_rescore_preserves_criteria_matches_and_other_fields_untouched(monkeypatch) -> None:
    document_id = uuid.uuid4()
    result = _base_result(pq_checklist=[{"category": "PAN", "tender_requirement": None,
                                          "company_value": None, "status": "pass",
                                          "page_ref": None}])
    analysis = _analysis(result, document_id)
    db = _FakeSession(analysis)
    document = Document(id=document_id, filename="t.pdf", status="ready")

    fresh = GoNoGoRescoreLLMResult(factor_scores=dict(_ALL_HIGH))
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda task, prompt, schema: (fresh, "test-model")
    )

    updated = reduce_pass.rescore_go_no_go(db, document, {})

    assert len(updated.result["criteria_matches"]) == 2
    assert updated.result["criteria_matches"][0]["human_override"]["status"] == "pass"
    assert updated.result["pq_checklist"][0]["category"] == "PAN"


def test_rescore_propagates_provider_error(monkeypatch) -> None:
    document_id = uuid.uuid4()
    analysis = _analysis(_base_result(), document_id)
    db = _FakeSession(analysis)
    document = Document(id=document_id, filename="t.pdf", status="ready")

    def _raise(task, prompt, schema):
        raise ProviderError("cloud and local both unavailable")

    monkeypatch.setattr(reduce_pass, "complete_structured", _raise)

    with pytest.raises(ProviderError):
        reduce_pass.rescore_go_no_go(db, document, {})
