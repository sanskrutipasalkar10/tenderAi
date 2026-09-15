"""Phase 5 gate: synopsis reduce-pass output — structure and citation presence.

golden_extraction.jsonl doubles as the source of truth for expected synopsis facts
(dates, amounts) since a synopsis is largely those same facts reassembled; no separate
golden_synopsis.jsonl is needed for v1 (see docs/SPEC.md §6 for the synopsis schema).

Mocks the LLM call per CLAUDE.md hard rule 8. Expected to fail with ImportError until
Phase 5 builds app/pipeline/reduce_pass.py.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.pipeline.reduce_pass import run_synopsis  # noqa: F401

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
DATASET = Path(__file__).parent / "datasets" / "golden_extraction.jsonl"

REQUIRED_SYNOPSIS_KEYS = {
    "title",
    "issuing_authority",
    "key_dates",
    "financials",
    "scope_summary",
    "eligibility_summary",
    "payment_terms_summary",
    "confidence",
}


@pytest.fixture(scope="module")
def extraction_rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


@patch("app.llm.client.complete")
def test_synopsis_has_required_shape(mock_complete, extraction_rows) -> None:
    fixtures = sorted({row["fixture"] for row in extraction_rows})
    for fixture_name in fixtures:
        mock_complete.return_value = {
            "title": "Test Tender",
            "issuing_authority": "Test Authority",
            "key_dates": [],
            "financials": [],
            "scope_summary": "...",
            "eligibility_summary": "...",
            "payment_terms_summary": "...",
            "confidence": "high",
        }
        result = run_synopsis(fixture_path=FIXTURES_DIR / f"{fixture_name}.pdf")
        missing = REQUIRED_SYNOPSIS_KEYS - result.keys()
        assert not missing, f"{fixture_name}: synopsis missing keys {missing}"
        for date_fact in result["key_dates"]:
            assert "page_ref" in date_fact, f"{fixture_name}: date fact missing page_ref"
        for amount_fact in result["financials"]:
            assert "page_ref" in amount_fact, f"{fixture_name}: financial fact missing page_ref"
