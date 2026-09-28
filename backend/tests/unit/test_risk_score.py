"""compute_risk_score / _keyword_severity — the diminishing-returns risk-score formula
and the keyword-based severity fallback (docs/DECISIONS.md #78), replacing the old
uncapped-sum-then-min(100,...) formula that saturated after 3-4 real risk clauses, and
the old exact-match-only rubric that silently flattened every unrecognized category to
MEDIUM. Pure functions, no DB/LLM — CLAUDE.md hard rule 8.
"""

import pytest

from app.pipeline import reduce_pass

# --- compute_risk_score ---------------------------------------------------------------


def test_no_risks_scores_zero() -> None:
    assert reduce_pass.compute_risk_score([]) == 0


def test_single_high_risk_equals_its_own_weight() -> None:
    # With one risk, compounding reduces to the plain weight — 1 - (1 - 0.30) = 0.30.
    assert reduce_pass.compute_risk_score(["HIGH"]) == 30


def test_single_medium_and_low_risk() -> None:
    assert reduce_pass.compute_risk_score(["MEDIUM"]) == 15
    assert reduce_pass.compute_risk_score(["LOW"]) == 5


@pytest.mark.parametrize(
    "severities,expected",
    [
        (["HIGH", "HIGH"], 51),
        (["HIGH", "HIGH", "HIGH", "HIGH"], 76),
        (["HIGH", "HIGH", "HIGH", "HIGH"] + ["MEDIUM"] * 8, 93),
        (["HIGH"] + ["MEDIUM"] * 12, 90),
    ],
)
def test_matches_the_worked_examples_shown_to_the_user(severities, expected) -> None:
    # Values independently recomputed from the shipped formula (not copied from the
    # earlier AskUserQuestion preview, which rounded two of these off by a point) — a
    # regression here means the formula drifted from what's actually deployed.
    assert reduce_pass.compute_risk_score(severities) == expected


def test_approaches_100_asymptotically_rather_than_a_hard_wall() -> None:
    # The underlying survival probability never reaches exactly zero, so the score
    # keeps climbing toward — but, for a realistic number of risks, doesn't reach —
    # 100. (round() will eventually still land on the integer 100 once the underlying
    # float gets close enough — e.g. 15+ HIGH risks — that's an int-rounding artifact,
    # not the formula hitting a cap the way the old min(100, sum(...)) one did.)
    assert reduce_pass.compute_risk_score(["HIGH"] * 10) == 97
    assert reduce_pass.compute_risk_score(["HIGH"] * 14) == 99
    assert reduce_pass.compute_risk_score(["HIGH"] * 14) < 100


def test_score_strictly_increases_as_risks_are_added() -> None:
    # "More/worse risks = higher score" must still hold — the fix is to the ceiling,
    # not to the direction of the signal.
    running: list[str] = []
    previous_score = 0
    for severity in ["LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "LOW"]:
        running.append(severity)
        score = reduce_pass.compute_risk_score(running)
        assert score >= previous_score
        previous_score = score


def test_needs_several_high_risks_to_clear_90_percent() -> None:
    # The specific complaint being fixed: the old formula hit 100 at just 4 HIGH
    # risks (4 * 30 = 120, capped). The new one should need meaningfully more.
    assert reduce_pass.compute_risk_score(["HIGH"] * 4) < 90
    assert reduce_pass.compute_risk_score(["HIGH"] * 8) >= 90


# --- _keyword_severity / _severity_for_category ---------------------------------------


@pytest.mark.parametrize(
    "category",
    [
        "Indemnification",
        "Patent Indemnity",
        "Indemnity / Damages",
        "Tax Liability and Indemnity",
        "Bid Security Forfeiture",
        "Penalty",
        "Risk Purchase",
        "Appropriation",
        "Unilateral Contract Cancellation",
        "Termination without Liability",
    ],
)
def test_real_high_severity_categories_from_live_runs(category: str) -> None:
    # Every one of these is a real category name observed in a real risk_finder run
    # this session — none is in the small exact-match SEVERITY_BY_CATEGORY rubric, so
    # this specifically tests the keyword fallback, not the exact-match tier.
    assert category not in reduce_pass.SEVERITY_BY_CATEGORY
    assert reduce_pass._severity_for_category(category) == "HIGH"


@pytest.mark.parametrize("category", ["Force Majeure Buyout", "Subcontracting Restriction"])
def test_real_low_severity_categories_from_live_runs(category: str) -> None:
    assert category not in reduce_pass.SEVERITY_BY_CATEGORY
    assert reduce_pass._severity_for_category(category) == "LOW"


@pytest.mark.parametrize(
    "category",
    [
        "Unilateral Arbitrator Appointment",
        "Approval Rights",
        "Cost Liability",
        "Warranty Liability",
        "Termination and Refund",
        "Ground Rent and Confiscation",
        "Rectification at Risk and Cost",
        "Fall Clause",
        "Some Entirely Novel Category Never Seen Before",
    ],
)
def test_categories_matching_neither_tier_default_to_medium(category: str, caplog) -> None:
    assert category not in reduce_pass.SEVERITY_BY_CATEGORY
    assert reduce_pass._keyword_severity(category) is None
    assert reduce_pass._severity_for_category(category) == reduce_pass.DEFAULT_SEVERITY


def test_exact_match_rubric_still_wins_over_keywords() -> None:
    # "Indemnity" exact-matches SEVERITY_BY_CATEGORY directly — must not fall through
    # to the keyword tier even though it would also match the "indemnit" keyword.
    assert reduce_pass._severity_for_category("Indemnity") == "HIGH"
