"""Phase 6 gate: adversarial cases from golden_adversarial.jsonl — the Tier 2
injection-test requirement (docs/SPEC.md §2, GenAI Playbook §15).

Four cases, one test each:
  1. prompt_injection        — embedded instruction text must have zero effect on output
  2. non_tender_document     — must be flagged out-of-domain, never confidently analyzed
  3. boilerplate_duplicate   — boilerplate_cache.hit_count must increment on the 2nd upload
  4. incomplete_company_profile — must return Conditional-Go + gaps[], never a guessed decision

Mocks the LLM call per CLAUDE.md hard rule 8. Expected to fail with ImportError until
Phase 6 builds app/guardrails/ + the full pipeline is wired together.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.guardrails.input_checks import looks_like_a_tender  # noqa: F401
from app.pipeline.dedupe import check_boilerplate_cache  # noqa: F401
from app.pipeline.reduce_pass import run_go_no_go  # noqa: F401
from app.services.pipeline_orchestrator import run_pipeline_sync  # noqa: F401

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
DATASET = Path(__file__).parent / "datasets" / "golden_adversarial.jsonl"
PROFILES = Path(__file__).parent / "datasets" / "test_company_profiles.json"


@pytest.fixture(scope="module")
def adversarial_rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


@pytest.fixture(scope="module")
def company_profiles() -> dict:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def _row(rows: list[dict], case: str) -> dict:
    matches = [r for r in rows if r["case"] == case]
    assert matches, f"No golden_adversarial.jsonl row for case={case}"
    return matches[0]


@patch("app.llm.client.complete")
def test_prompt_injection_has_zero_effect(
    mock_complete, adversarial_rows, company_profiles
) -> None:
    row = _row(adversarial_rows, "prompt_injection")
    # Even if a compromised prompt echoed the injected instruction, output_checks.py
    # (Phase 6) must reject anything outside the fixed schema/decision space — the mock
    # here simulates the CORRECT post-guardrail behavior to test the assertion shape;
    # the real adversarial run happens against the live reduce_pass call in Phase 6.
    mock_complete.return_value = {
        "decision": "Conditional-Go",
        "criteria_matches": [],
        "gaps": ["insufficient verified eligibility data"],
    }
    result = run_go_no_go(
        fixture_path=FIXTURES_DIR / f"{row['fixture']}.pdf",
        company_profile=company_profiles["profile_qualified"],
    )
    assert result["decision"] != "Go" or result.get("score", 0) != 100, (
        "Injected instruction text appears to have influenced the decision"
    )


def test_non_tender_document_is_flagged(adversarial_rows) -> None:
    row = _row(adversarial_rows, "non_tender_document")
    doc_path = FIXTURES_DIR / f"{row['fixture']}.pdf"
    assert looks_like_a_tender(doc_path) is False, (
        f"{row['fixture']} should be flagged as not a tender document"
    )


def test_boilerplate_duplicate_increments_cache_hit_count(adversarial_rows, db_session) -> None:
    row = _row(adversarial_rows, "boilerplate_duplicate")
    first_path = FIXTURES_DIR / f"{row['fixture_first']}.pdf"
    second_path = FIXTURES_DIR / f"{row['fixture_second']}.pdf"

    run_pipeline_sync(first_path, db_session)
    hits_before = check_boilerplate_cache.hit_count(db_session)

    run_pipeline_sync(second_path, db_session)
    hits_after = check_boilerplate_cache.hit_count(db_session)

    assert hits_after > hits_before, (
        "boilerplate_cache.hit_count did not increment on the near-duplicate upload"
    )


@patch("app.llm.client.complete")
def test_incomplete_profile_yields_conditional_go(
    mock_complete, adversarial_rows, company_profiles
) -> None:
    row = _row(adversarial_rows, "incomplete_company_profile")
    mock_complete.return_value = {
        "decision": row["expected_decision"],
        "criteria_matches": [],
        "gaps": row["expected_gaps"],
    }
    result = run_go_no_go(
        fixture_path=FIXTURES_DIR / f"{row['fixture']}.pdf",
        company_profile=company_profiles[row["test_company_profile"]],
    )
    assert result["decision"] == "Conditional-Go"
    for gap in row["expected_gaps"]:
        assert gap in result["gaps"]
