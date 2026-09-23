"""apply_human_overrides — pure code, no LLM, no DB. Applies a bid-team member's
review of specific eligibility criteria to an already-computed go_no_go result dict
and recomputes decision/gaps/score, without ever touching factor_scores (a stated
scope boundary — see docs/DECISIONS.md).
"""

import pytest

from app.core.exceptions import DataQualityError
from app.pipeline import reduce_pass

_FACTOR_SCORES_ALL_HIGH = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 90)


def _base_result(**overrides) -> dict:
    base = {
        "score": 90,
        "decision": "Go",
        "criteria_matches": [
            {
                "criterion": "Mandatory ISO 9001 certification",
                "required": "ISO 9001:2015",
                "company_value": "No relevant information in company profile",
                "status": "insufficient_data",
                "page_ref": 2,
                "gate": "Mandatory certification unavailable",
                "criterion_type": "eligibility",
                "human_override": None,
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
        "gaps": ["Mandatory certification unavailable"],
        "next_steps": [],
        "factor_scores": dict(_FACTOR_SCORES_ALL_HIGH),
    }
    base.update(overrides)
    return base


def test_overriding_a_gate_tagged_criterion_to_pass_flips_decision() -> None:
    result = _base_result(score=0, decision="No-Go")

    updated = reduce_pass.apply_human_overrides(
        result, [(0, "pass", "Confirmed via certificate on file")]
    )

    assert updated["gaps"] == []
    assert updated["decision"] == "Go"  # weighted score of all-90s bands to Go
    assert updated["criteria_matches"][0]["human_override"]["status"] == "pass"
    assert updated["criteria_matches"][0]["human_override"]["original_status"] == (
        "insufficient_data"
    )
    assert updated["criteria_matches"][0]["human_override"]["note"] == (
        "Confirmed via certificate on file"
    )


def test_overriding_to_fail_keeps_the_gate_triggered() -> None:
    result = _base_result(score=0, decision="No-Go")

    updated = reduce_pass.apply_human_overrides(result, [(0, "fail", None)])

    assert updated["decision"] == "No-Go"
    assert updated["gaps"] == ["Mandatory certification unavailable"]


def test_factor_scores_are_never_touched_by_an_override() -> None:
    result = _base_result(score=0, decision="No-Go")
    original_factor_scores = dict(result["factor_scores"])

    updated = reduce_pass.apply_human_overrides(result, [(0, "pass", None)])

    assert updated["factor_scores"] == original_factor_scores


def test_out_of_range_index_raises_data_quality_error() -> None:
    result = _base_result()
    with pytest.raises(DataQualityError, match="out of range"):
        reduce_pass.apply_human_overrides(result, [(5, "pass", None)])


def test_reviewing_a_procedural_criterion_raises_data_quality_error() -> None:
    result = _base_result()
    with pytest.raises(DataQualityError, match="procedural"):
        reduce_pass.apply_human_overrides(result, [(1, "pass", None)])


def test_short_circuit_result_with_no_factor_scores_is_untouched_by_score_recompute() -> None:
    """A missing-profile-fields / no-criteria short-circuit result never computed a
    weighted score — an override there can only confirm the existing decision, never
    manufacture a score. (Reviewing a procedural criterion in this state would still
    raise, but this covers the None-factor_scores branch specifically.)
    """
    result = _base_result(
        score=0,
        decision="Conditional-Go (Partner Required)",
        factor_scores=None,
        criteria_matches=[
            {
                "criterion": "Mandatory ISO 9001 certification",
                "required": "ISO 9001:2015",
                "company_value": "No relevant information in company profile",
                "status": "insufficient_data",
                "page_ref": 2,
                "gate": None,
                "criterion_type": "eligibility",
                "human_override": None,
            }
        ],
    )

    updated = reduce_pass.apply_human_overrides(result, [(0, "pass", None)])

    assert updated["score"] == 0
    assert updated["decision"] == "Conditional-Go (Partner Required)"
    assert updated["factor_scores"] is None


def test_multiple_overrides_applied_in_one_call() -> None:
    result = _base_result(
        score=0,
        decision="No-Go",
        gaps=["Mandatory certification unavailable", "Turnover not met and no valid exemption"],
        criteria_matches=[
            {
                "criterion": "Mandatory ISO 9001 certification",
                "required": "ISO 9001:2015",
                "company_value": "No relevant information",
                "status": "insufficient_data",
                "page_ref": 2,
                "gate": "Mandatory certification unavailable",
                "criterion_type": "eligibility",
                "human_override": None,
            },
            {
                "criterion": "Minimum turnover INR 5 Cr",
                "required": "INR 5 Cr",
                "company_value": "INR 2 Cr",
                "status": "fail",
                "page_ref": 4,
                "gate": "Turnover not met and no valid exemption",
                "criterion_type": "eligibility",
                "human_override": None,
            },
        ],
    )

    updated = reduce_pass.apply_human_overrides(
        result, [(0, "pass", "Certificate on file"), (1, "fail", "Genuinely short of turnover")]
    )

    assert updated["gaps"] == ["Turnover not met and no valid exemption"]
    assert updated["decision"] == "No-Go"  # the turnover gate still triggers
    assert updated["criteria_matches"][0]["human_override"]["status"] == "pass"
    assert updated["criteria_matches"][1]["human_override"]["status"] == "fail"
