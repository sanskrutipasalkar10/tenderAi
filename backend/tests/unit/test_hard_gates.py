"""check_hard_gates — pure code, no LLM, no DB (docs/pq-tq-framework-implementation-
plan.md §3, docs/DECISIONS.md). Each of the 7 gates is engineered to trip
individually, plus the "an untagged failure doesn't spuriously trigger a gate" and
"multiple gates at once" cases. Also covers the criterion_type/human_override
follow-up (docs/DECISIONS.md): a "procedural" criterion must never trigger a gate
even if (incorrectly) tagged, "insufficient_data" triggers exactly like "fail", and a
human_override's status always wins over the model's original status.
"""

from datetime import datetime, timezone

from app.models.schemas import (
    GoNoGoCriterionMatch,
    GoNoGoCriterionType,
    GoNoGoHumanOverride,
    GoNoGoStatus,
)
from app.pipeline import reduce_pass


def _match(
    status: GoNoGoStatus,
    gate: str | None,
    criterion_type: GoNoGoCriterionType = "eligibility",
    human_override: GoNoGoHumanOverride | None = None,
) -> GoNoGoCriterionMatch:
    return GoNoGoCriterionMatch(
        criterion="c",
        required="r",
        company_value="v",
        status=status,
        page_ref=1,
        gate=gate,
        criterion_type=criterion_type,
        human_override=human_override,
    )


def test_no_failures_triggers_no_gates() -> None:
    matches = [_match("pass", None), _match("pass", None)]
    assert reduce_pass.check_hard_gates(matches) == []


def test_untagged_failure_triggers_no_gate() -> None:
    """A criterion can fail without forcing No-Go — only a gate-tagged fail does
    (docs/DECISIONS.md's Phase 1 row, the real behavior change from "any fail blocks").
    """
    matches = [_match("fail", None)]
    assert reduce_pass.check_hard_gates(matches) == []


def test_each_gate_triggers_individually() -> None:
    for gate in reduce_pass.HARD_FAIL_GATES:
        matches = [_match("fail", gate)]
        assert reduce_pass.check_hard_gates(matches) == [gate], gate


def test_gate_only_counts_on_a_failed_match() -> None:
    """A gate name on a "pass" status match is not something the prompt should ever
    produce, but if it did, it must not trigger — gates only mean something on a
    failure.
    """
    matches = [_match("pass", reduce_pass.HARD_FAIL_GATES[0])]
    assert reduce_pass.check_hard_gates(matches) == []


def test_multiple_gates_all_returned_in_canonical_order() -> None:
    gate_a, gate_b = reduce_pass.HARD_FAIL_GATES[3], reduce_pass.HARD_FAIL_GATES[0]
    matches = [_match("fail", gate_a), _match("fail", gate_b), _match("pass", None)]
    # Returned in HARD_FAIL_GATES' own order, not insertion order.
    assert reduce_pass.check_hard_gates(matches) == [gate_b, gate_a]


def test_same_gate_from_two_criteria_is_not_duplicated() -> None:
    gate = reduce_pass.HARD_FAIL_GATES[0]
    matches = [_match("fail", gate), _match("fail", gate)]
    assert reduce_pass.check_hard_gates(matches) == [gate]


def test_procedural_criterion_never_triggers_a_gate() -> None:
    """Defense in depth (CLAUDE.md hard rule 3): even if the model incorrectly tags a
    procedural criterion with a gate, code must not honor it.
    """
    gate = reduce_pass.HARD_FAIL_GATES[0]
    matches = [_match("fail", gate, criterion_type="procedural")]
    assert reduce_pass.check_hard_gates(matches) == []


def test_insufficient_data_triggers_a_gate_like_fail() -> None:
    """"We don't know" is never a free pass by default — matches the source
    framework's "do not mark qualified without documentary evidence" stance.
    """
    gate = reduce_pass.HARD_FAIL_GATES[0]
    matches = [_match("insufficient_data", gate)]
    assert reduce_pass.check_hard_gates(matches) == [gate]


def test_human_override_to_pass_un_triggers_a_gate() -> None:
    gate = reduce_pass.HARD_FAIL_GATES[0]
    override = GoNoGoHumanOverride(
        status="pass",
        note="Confirmed via CV on file",
        original_status="insufficient_data",
        reviewed_at=datetime.now(timezone.utc),
    )
    matches = [_match("insufficient_data", gate, human_override=override)]
    assert reduce_pass.check_hard_gates(matches) == []


def test_human_override_to_fail_still_triggers_a_gate() -> None:
    gate = reduce_pass.HARD_FAIL_GATES[0]
    override = GoNoGoHumanOverride(
        status="fail",
        note="Checked — no such certificate on file",
        original_status="insufficient_data",
        reviewed_at=datetime.now(timezone.utc),
    )
    matches = [_match("insufficient_data", gate, human_override=override)]
    assert reduce_pass.check_hard_gates(matches) == [gate]
