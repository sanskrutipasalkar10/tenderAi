"""compute_tq_score / _run_tq_scoring — pure code + a mocked LLM call, no DB
(docs/DECISIONS.md). Informational only, mirrors test_pq_checklist.py and
test_weighted_score_reproducibility.py's patterns. A failure here must never block
the main go_no_go decision (same resilience principle as docs/DECISIONS.md #62).
"""

import uuid

import pytest

from app.core.exceptions import ProviderError
from app.models.schemas import MapPassResult, TQScoringLLMResult
from app.pipeline import reduce_pass


def test_tq_factor_weights_sums_to_100() -> None:
    assert sum(reduce_pass.TQ_FACTOR_WEIGHTS.values()) == 100


def test_tq_factor_weights_has_exactly_12_entries() -> None:
    assert len(reduce_pass.TQ_FACTOR_WEIGHTS) == 12


def test_compute_tq_score_all_factors_at_100_scores_100() -> None:
    scores = dict.fromkeys(reduce_pass.TQ_FACTOR_WEIGHTS, 100)
    assert reduce_pass.compute_tq_score(scores) == 100


def test_compute_tq_score_all_factors_at_0_scores_0() -> None:
    scores = dict.fromkeys(reduce_pass.TQ_FACTOR_WEIGHTS, 0)
    assert reduce_pass.compute_tq_score(scores) == 0


def test_compute_tq_score_exact_weighted_sum() -> None:
    scores = dict.fromkeys(reduce_pass.TQ_FACTOR_WEIGHTS, 50)
    # Every factor at 50, weights sum to 100 -> weighted sum is exactly 50.
    assert reduce_pass.compute_tq_score(scores) == pytest.approx(50)


def test_compute_tq_score_missing_factor_raises() -> None:
    scores = dict.fromkeys(reduce_pass.TQ_FACTOR_WEIGHTS, 50)
    del scores["Key Personnel"]
    with pytest.raises(ValueError, match="Key Personnel"):
        reduce_pass.compute_tq_score(scores)


def _fake_tq_result() -> TQScoringLLMResult:
    return TQScoringLLMResult(
        factor_scores=dict.fromkeys(reduce_pass.TQ_FACTOR_WEIGHTS, 70),
        commercial_competitiveness="HIGH",
        bid_preparation_effort="LOW",
        major_qualification_gap="None identified",
        major_technical_gap="None identified",
    )


def test_run_tq_scoring_returns_none_on_provider_error(monkeypatch) -> None:
    def _raise(task, prompt, schema):
        raise ProviderError("cloud and local both unavailable")

    monkeypatch.setattr(reduce_pass, "complete_structured", _raise)

    result = reduce_pass._run_tq_scoring(MapPassResult(), {}, uuid.uuid4())

    assert result is None


def test_run_tq_scoring_returns_full_result_on_success(monkeypatch) -> None:
    fake = _fake_tq_result()
    monkeypatch.setattr(
        reduce_pass, "complete_structured", lambda task, prompt, schema: (fake, "test-model")
    )

    result = reduce_pass._run_tq_scoring(MapPassResult(), {}, uuid.uuid4())

    assert result is not None
    assert result.commercial_competitiveness == "HIGH"
    assert result.bid_preparation_effort == "LOW"
    assert set(result.factor_scores) == set(reduce_pass.TQ_FACTOR_WEIGHTS)


def test_run_tq_scoring_returns_none_on_missing_factors(monkeypatch) -> None:
    """A model that omits a TQ factor degrades gracefully (None), same as a
    ProviderError — compute_tq_score would otherwise raise and, unlike the PQ
    checklist's partial-is-fine stance, a TQ score with a missing factor can't be
    meaningfully computed at all.
    """
    incomplete = TQScoringLLMResult(
        factor_scores={"Key Personnel": 70},  # only 1 of 12
        commercial_competitiveness="MEDIUM",
        bid_preparation_effort="MEDIUM",
        major_qualification_gap="None identified",
        major_technical_gap="None identified",
    )
    monkeypatch.setattr(
        reduce_pass,
        "complete_structured",
        lambda task, prompt, schema: (incomplete, "test-model"),
    )

    result = reduce_pass._run_tq_scoring(MapPassResult(), {}, uuid.uuid4())

    assert result is None
