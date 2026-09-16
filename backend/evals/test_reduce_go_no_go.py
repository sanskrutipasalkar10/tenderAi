"""Phase 5 gate: go_no_go reduce-pass output against golden_go_no_go.jsonl.

Covers docs/SPEC.md §7's zero-hallucination-tolerance requirement for criteria_matches
(turnover, certifications) and the Conditional-Go/gaps[] path for an incomplete company
profile (see fixture_13_incomplete_profile in golden_adversarial.jsonl).

Rewritten against the real, Phase-4/5-verified architecture: reduce_pass.run_go_no_go
takes a (db, document, company_profile), reading already-persisted chunk_extractions —
not a raw PDF fixture path (no run_pipeline_sync/vision/classification exists to call
here; that's Phase 6's full-pipeline integration, exercised for real in
tests/integration/, not this $0/deterministic eval). Mocks complete_structured (the
same seam app.pipeline.map_pass's own tests mock), per CLAUDE.md hard rule 8.
"""

import json
import uuid
from pathlib import Path

import pytest

from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.schemas import (
    GoNoGoCriterionMatch,
    GoNoGoLLMResult,
    MapPassCriterionFact,
    MapPassResult,
)
from app.pipeline import reduce_pass

DATASET = Path(__file__).parent / "datasets" / "golden_go_no_go.jsonl"
PROFILES = Path(__file__).parent / "datasets" / "test_company_profiles.json"


class _FakeListQuery:
    def __init__(self, items: list) -> None:
        self._items = items

    def filter(self, *_conditions):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _FakeGoldenSession:
    """Seeds one ChunkExtraction whose criteria facts are exactly the golden row's
    criteria (so the reduce pass reads real, page-tagged map-pass-shaped facts, the
    same way it would from a real Phase-4 run) and nothing else — a real DocumentAnalysis
    row/DB is not needed to exercise this module's decision logic.
    """

    def __init__(self, criteria: list[MapPassCriterionFact]) -> None:
        extraction = ChunkExtraction(
            id=uuid.uuid4(),
            chunk_id=uuid.uuid4(),
            structured_json=MapPassResult(criteria=criteria).model_dump(),
        )
        self._chunks = [Chunk(id=extraction.chunk_id, document_id=uuid.uuid4())]
        self._chunk_extractions = [extraction]
        self.added: list = []

    def query(self, model):
        if model is Chunk:
            return _FakeListQuery(self._chunks)
        if model is ChunkExtraction:
            return _FakeListQuery(self._chunk_extractions)
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


@pytest.fixture(scope="module")
def company_profiles() -> dict:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def test_go_no_go_decision_matches_golden(monkeypatch, golden_rows, company_profiles) -> None:
    for row in golden_rows:
        profile = company_profiles[row["test_company_profile"]]
        criteria = [
            MapPassCriterionFact(description=m["criterion"], page_ref=row["eligibility_page"])
            for m in row["expected_criteria_matches"]
        ]
        db = _FakeGoldenSession(criteria)
        document = Document(id=uuid.uuid4(), filename=f"{row['fixture']}.pdf", status="analyzing")

        fake_llm_result = GoNoGoLLMResult(
            criteria_matches=[
                GoNoGoCriterionMatch(
                    criterion=m["criterion"],
                    required=m["required"],
                    company_value=m["company_value"],
                    status=m["status"],
                    page_ref=row["eligibility_page"],
                )
                for m in row["expected_criteria_matches"]
            ]
        )
        monkeypatch.setattr(
            reduce_pass,
            "complete_structured",
            lambda *a, r=fake_llm_result, **k: (r, "test-model"),
        )

        analysis = reduce_pass.run_go_no_go(db, document, profile)

        assert analysis.result["decision"] == row["expected_decision"], row["fixture"]
        # `gaps[]` is reserved for the "missing company_profile fields" Conditional-Go
        # path (docs/SPEC.md §7) — golden_adversarial.jsonl's incomplete_company_profile
        # case covers that directly. fixture_12's own `expected_gaps` is a narrative
        # explanation for a plain criteria-fail No-Go (authored before this
        # architecture existed, in Phase 1) rather than a missing-field list, so it's
        # not checked here; the criteria_matches themselves already carry that reasoning
        # (required vs. company_value on the failing criterion).
        if row["expected_decision"] == "Conditional-Go":
            assert analysis.result["gaps"] == row["expected_gaps"], row["fixture"]
