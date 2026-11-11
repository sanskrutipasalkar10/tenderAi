"""Unit tests for reduce_pass.final_decision — a failed eligibility criterion caps the
score band's decision (docs/DECISIONS.md #95)."""

from datetime import datetime, timezone

from app.models.schemas import ConsortiumPolicy, GoNoGoCriterionMatch, GoNoGoHumanOverride
from app.pipeline.reduce_pass import apply_human_overrides, final_decision

ALLOWED = ConsortiumPolicy(
    status="allowed", quote="Consortium participation is allowed.", page_ref=34
)
NOT_ALLOWED = ConsortiumPolicy(status="not_allowed", quote="Consortium not allowed.", page_ref=3)


def _match(status: str, criterion_type: str = "eligibility", **kw) -> GoNoGoCriterionMatch:
    return GoNoGoCriterionMatch(
        criterion="Training projects worth 200 Lakh for Govt/PSU in last 3 years",
        required="200 Lakh",
        company_value="4.46 Lakh",
        status=status,
        page_ref=25,
        criterion_type=criterion_type,
        **kw,
    )


def test_no_failed_criterion_keeps_the_score_band() -> None:
    assert final_decision(65, [], [_match("pass")], ALLOWED) == ("Go (Management Review)", None)


def test_failed_criterion_caps_go_at_conditional_when_consortium_allowed() -> None:
    decision, reason = final_decision(65, [], [_match("fail")], ALLOWED)

    assert decision == "Conditional-Go (Partner Required)"
    assert reason is not None and "Go (Management Review)" in reason
    assert "allows consortium" in reason


def test_failed_criterion_is_no_go_when_consortium_not_allowed() -> None:
    decision, reason = final_decision(85, [], [_match("fail")], NOT_ALLOWED)

    assert decision == "No-Go"
    assert reason is not None and "doesn't allow" in reason


def test_unknown_policy_still_caps_and_says_to_confirm() -> None:
    decision, reason = final_decision(90, [], [_match("fail")], None)

    assert decision == "Conditional-Go (Partner Required)"
    assert reason is not None and "confirm with the buyer" in reason


def test_a_score_already_below_the_cap_is_unchanged() -> None:
    assert final_decision(40, [], [_match("fail")], ALLOWED) == ("No-Go", None)


def test_procedural_and_insufficient_data_criteria_never_cap() -> None:
    matches = [_match("fail", criterion_type="procedural"), _match("insufficient_data")]

    assert final_decision(85, [], matches, ALLOWED) == ("Go", None)


def test_a_human_mark_eligible_lifts_the_cap() -> None:
    reviewed = _match(
        "fail",
        human_override=GoNoGoHumanOverride(
            status="pass", original_status="fail", reviewed_at=datetime.now(timezone.utc)
        ),
    )

    assert final_decision(65, [], [reviewed], ALLOWED) == ("Go (Management Review)", None)


def test_apply_human_overrides_recomputes_the_cap() -> None:
    factor_scores = {
        "PQ Eligibility": 65, "Similar Experience": 65, "Technical Capability": 65,
        "Government/PSU Experience": 65, "Key Manpower": 65, "Financial Capability": 65,
        "Strategic Relevance": 65, "Partner/OEM Availability": 65,
    }
    result = {
        "score": 65,
        "decision": "Conditional-Go (Partner Required)",
        "decision_cap_reason": "capped",
        "criteria_matches": [_match("fail").model_dump(mode="json")],
        "gaps": [],
        "factor_scores": factor_scores,
        "consortium_policy": ALLOWED.model_dump(),
    }

    updated = apply_human_overrides(result, [(0, "pass", "P-16 includes training")])

    assert updated["decision"] == "Go (Management Review)"
    assert updated["decision_cap_reason"] is None
