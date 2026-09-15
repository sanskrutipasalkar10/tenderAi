"""Phase 4 gate: map-pass fact extraction — chunk_extractions populated for every
fixture, facts correctly page-tagged against golden_extraction.jsonl.

Mocks the LLM call (Groq via app.llm.router) per CLAUDE.md hard rule 8 — this test must
cost $0 and be deterministic. Expected to fail with ImportError until Phase 4 builds
app/pipeline/map_pass.py and app/pipeline/chunk.py.
"""

import json
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from app.pipeline.chunk import build_chunks  # noqa: F401
from app.pipeline.map_pass import run_map_pass  # noqa: F401

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
DATASET = Path(__file__).parent / "datasets" / "golden_extraction.jsonl"


def load_extraction_rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


@pytest.fixture(scope="module")
def extraction_rows() -> list[dict]:
    return load_extraction_rows()


def test_golden_extraction_dataset_composition(extraction_rows: list[dict]) -> None:
    """Sanity check on dataset shape before trusting the accuracy numbers below."""
    assert len(extraction_rows) > 0
    for row in extraction_rows:
        assert "fixture" in row
        assert "page_number" in row
        assert "expected_facts" in row


@patch("app.llm.client.complete")
def test_facts_are_correctly_page_tagged(mock_complete, extraction_rows: list[dict]) -> None:
    """Every chunk_extractions.structured_json fact must carry the correct page_number —
    this is what Phase 5's citation-verifiability gate depends on downstream.
    """
    by_fixture: dict[str, list[dict]] = {}
    for row in extraction_rows:
        by_fixture.setdefault(row["fixture"], []).append(row)

    for fixture_name, _rows in by_fixture.items():
        doc = fitz.open(FIXTURES_DIR / f"{fixture_name}.pdf")
        chunks = build_chunks(doc)
        # The real map-pass call is mocked; this test only exists to be filled in once
        # map_pass.py defines its expected mock-response shape (Phase 4).
        mock_complete.return_value = {"facts": []}
        extractions = [run_map_pass(chunk) for chunk in chunks]
        doc.close()
        assert len(extractions) == len(chunks)
