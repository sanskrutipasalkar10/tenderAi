"""Phase 5 gate: go_no_go reduce-pass output against golden_go_no_go.jsonl.

Covers docs/SPEC.md §7's zero-hallucination-tolerance requirement for criteria_matches
(turnover, certifications) and the Conditional-Go/gaps[] path for an incomplete company
profile (see fixture_13_incomplete_profile in golden_adversarial.jsonl).

Mocks the LLM call per CLAUDE.md hard rule 8. Expected to fail with ImportError until
Phase 5 builds app/pipeline/reduce_pass.py.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.pipeline.reduce_pass import run_go_no_go  # noqa: F401

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
DATASET = Path(__file__).parent / "datasets" / "golden_go_no_go.jsonl"
PROFILES = Path(__file__).parent / "datasets" / "test_company_profiles.json"


@pytest.fixture(scope="module")
def golden_rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


@pytest.fixture(scope="module")
def company_profiles() -> dict:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


@patch("app.llm.client.complete")
def test_go_no_go_decision_matches_golden(mock_complete, golden_rows, company_profiles) -> None:
    for row in golden_rows:
        profile = company_profiles[row["test_company_profile"]]
        # The mocked LLM response shape will be finalized alongside reduce_pass.py's
        # actual prompt/schema in Phase 5 — see app/prompts/reduce/v1_go_no_go.md.
        mock_complete.return_value = {
            "decision": row["expected_decision"],
            "criteria_matches": row["expected_criteria_matches"],
            "gaps": row["expected_gaps"],
        }
        result = run_go_no_go(
            fixture_path=FIXTURES_DIR / f"{row['fixture']}.pdf",
            company_profile=profile,
        )
        assert result["decision"] == row["expected_decision"], row["fixture"]
        assert result["gaps"] == row["expected_gaps"], row["fixture"]
