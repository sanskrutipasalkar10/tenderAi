"""Phase 5 gate: risk_finder reduce-pass output against golden_risk_finder.jsonl —
expected category/severity/page_ref per known risky clause.

Rewritten against the real architecture (see evals/test_reduce_go_no_go.py's module
docstring for why): reduce_pass.run_risk_finder(db, document) reads already-persisted
chunk_extractions, and severity is assigned by reduce_pass.SEVERITY_BY_CATEGORY (code,
not the model — CLAUDE.md hard rule 3), so this eval's real job is checking that rubric
against the golden category->severity mapping, not just checking pass-through. Mocks
complete_structured per CLAUDE.md hard rule 8.
"""

import json
import uuid
from collections import defaultdict
from pathlib import Path

import pytest

from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.page import Page
from app.models.schemas import (
    MapPassResult,
    MapPassRiskCandidate,
    RiskFinderLLMResult,
    RiskFinderLLMRisk,
)
from app.pipeline import reduce_pass

DATASET = Path(__file__).parent / "datasets" / "golden_risk_finder.jsonl"


class _FakeListQuery:
    def __init__(self, items: list) -> None:
        self._items = items

    def filter(self, *_conditions):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _FakePageQuery:
    """Every golden page_ref is treated as resolvable — this eval is about
    category/severity correctness, not citation resolution (that's
    test_citation_verifiability.py's job) — so every risk comes back verified.
    """

    def filter(self, *_conditions):
        return self

    def first(self):
        return Page(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            page_number=0,
            classification="native_text",
        )


class _FakeGoldenSession:
    def __init__(self, risk_candidates: list[MapPassRiskCandidate]) -> None:
        extraction = ChunkExtraction(
            id=uuid.uuid4(),
            chunk_id=uuid.uuid4(),
            structured_json=MapPassResult(risk_candidates=risk_candidates).model_dump(),
        )
        self._chunks = [Chunk(id=extraction.chunk_id, document_id=uuid.uuid4())]
        self._chunk_extractions = [extraction]
        self.added: list = []

    def query(self, model):
        if model is Chunk:
            return _FakeListQuery(self._chunks)
        if model is ChunkExtraction:
            return _FakeListQuery(self._chunk_extractions)
        if model is Page:
            return _FakePageQuery()
        if model is DocumentAnalysis:
            return _FakeListQuery([])
        raise AssertionError(f"Unexpected query for {model}")

    def add(self, obj) -> None:
        if isinstance(obj, DocumentAnalysis) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


@pytest.fixture(scope="module")
def golden_rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


def test_known_risks_are_found_with_correct_category_and_severity(monkeypatch, golden_rows) -> None:
    by_fixture: dict[str, list[dict]] = defaultdict(list)
    for row in golden_rows:
        by_fixture[row["fixture"]].append(row)

    for fixture_name, expected_risks in by_fixture.items():
        candidates = [
            MapPassRiskCandidate(
                category=r["expected_category"],
                clause_summary=f"Test clause for {r['expected_category']}",
                page_ref=r["page_number"],
            )
            for r in expected_risks
        ]
        db = _FakeGoldenSession(candidates)
        document = Document(id=uuid.uuid4(), filename=f"{fixture_name}.pdf", status="analyzing")

        fake_llm_result = RiskFinderLLMResult(
            risks=[
                RiskFinderLLMRisk(
                    category=r["expected_category"],
                    clause_summary=f"Test clause for {r['expected_category']}",
                    page_ref=r["page_number"],
                )
                for r in expected_risks
            ]
        )
        monkeypatch.setattr(
            reduce_pass,
            "complete_structured",
            lambda *a, r=fake_llm_result, **k: (r, "test-model"),
        )

        analysis = reduce_pass.run_risk_finder(db, document)

        found = {(r["category"], r["page_ref"], r["severity"]) for r in analysis.result["risks"]}
        expected = {
            (r["expected_category"], r["page_number"], r["expected_severity"])
            for r in expected_risks
        }
        assert found == expected, fixture_name
