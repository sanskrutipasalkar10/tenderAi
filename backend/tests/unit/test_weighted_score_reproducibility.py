"""compute_weighted_score / decide — pure arithmetic (docs/pq-tq-framework-
implementation-plan.md §4, docs/DECISIONS.md), so this is a fast deterministic unit
test, not a golden-dataset LLM eval. Fixed inputs must always produce the exact same
output — that reproducibility is the entire point of replacing a freeform score.
"""

import pytest

from app.pipeline import reduce_pass


def test_all_factors_at_100_scores_100() -> None:
    scores = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 100)
    assert reduce_pass.compute_weighted_score(scores) == 100


def test_all_factors_at_0_scores_0() -> None:
    scores = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 0)
    assert reduce_pass.compute_weighted_score(scores) == 0


def test_exact_weighted_sum_for_a_known_mix() -> None:
    # PQ Eligibility=30, Similar Experience=20, Technical Capability=15,
    # Government/PSU Experience=10, Key Manpower=10, Financial Capability=5,
    # Strategic Relevance=5, Partner/OEM Availability=5 (sums to 100).
    scores = {
        "PQ Eligibility": 90,
        "Similar Experience": 70,
        "Technical Capability": 80,
        "Government/PSU Experience": 100,
        "Key Manpower": 60,
        "Financial Capability": 40,
        "Strategic Relevance": 50,
        "Partner/OEM Availability": 20,
    }
    expected = (
        90 * 30 + 70 * 20 + 80 * 15 + 100 * 10 + 60 * 10 + 40 * 5 + 50 * 5 + 20 * 5
    ) / 100
    assert reduce_pass.compute_weighted_score(scores) == pytest.approx(expected)


def test_missing_factor_raises_rather_than_silently_scoring_low() -> None:
    scores = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 50)
    del scores["Key Manpower"]
    with pytest.raises(ValueError, match="Key Manpower"):
        reduce_pass.compute_weighted_score(scores)


@pytest.mark.parametrize(
    ("score", "expected_decision"),
    [
        (100, "Go"),
        (80, "Go"),
        (79.9, "Go (Management Review)"),
        (65, "Go (Management Review)"),
        (64.9, "Conditional-Go (Partner Required)"),
        (50, "Conditional-Go (Partner Required)"),
        (49.9, "No-Go"),
        (0, "No-Go"),
    ],
)
def test_decide_bands_match_the_framework_exactly(score, expected_decision) -> None:
    assert reduce_pass.decide(score) == expected_decision
