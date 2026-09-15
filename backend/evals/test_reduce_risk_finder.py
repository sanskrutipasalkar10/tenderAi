"""Phase 5 gate: risk_finder reduce-pass output against golden_risk_finder.jsonl —
expected category/severity/page_ref per known risky clause.

Mocks the LLM call per CLAUDE.md hard rule 8. Expected to fail with ImportError until
Phase 5 builds app/pipeline/reduce_pass.py.
"""

import json
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

import pytest

from app.pipeline.reduce_pass import run_risk_finder  # noqa: F401

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
DATASET = Path(__file__).parent / "datasets" / "golden_risk_finder.jsonl"


@pytest.fixture(scope="module")
def golden_rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


@patch("app.llm.client.complete")
def test_known_risks_are_found_with_correct_page_ref(mock_complete, golden_rows) -> None:
    by_fixture: dict[str, list[dict]] = defaultdict(list)
    for row in golden_rows:
        by_fixture[row["fixture"]].append(row)

    for fixture_name, expected_risks in by_fixture.items():
        mock_complete.return_value = {
            "risk_score": 50,
            "risks": [
                {
                    "category": r["expected_category"],
                    "clause_summary": f"Test clause for {r['expected_category']}",
                    "severity": r["expected_severity"],
                    "page_ref": r["page_number"],
                    "verified": True,
                }
                for r in expected_risks
            ],
        }
        result = run_risk_finder(fixture_path=FIXTURES_DIR / f"{fixture_name}.pdf")

        found_categories = {(r["category"], r["page_ref"]) for r in result["risks"]}
        expected_categories = {(r["expected_category"], r["page_number"]) for r in expected_risks}
        missing = expected_categories - found_categories
        assert not missing, f"{fixture_name}: missing expected risks {missing}"
