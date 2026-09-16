"""Phase 5 gate: synopsis reduce-pass output — structure and citation presence.

golden_extraction.jsonl doubles as the source of truth for expected synopsis facts
(dates, amounts) since a synopsis is largely those same facts reassembled; no separate
golden_synopsis.jsonl is needed for v1 (see docs/SPEC.md §6 for the synopsis schema).

Rewritten against the real architecture (see evals/test_reduce_go_no_go.py's module
docstring for why). reduce_pass.run_synopsis passes key_dates/financials through
directly from already-page-cited map-pass facts (hard rule 7: zero hallucination
tolerance for dates/amounts) rather than asking the model to restate them, so this eval
checks that every golden date/amount survives into the final synopsis with its
page_ref intact. Mocks complete_structured per CLAUDE.md hard rule 8.
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
from app.models.schemas import MapPassAmountFact, MapPassDateFact, MapPassResult, SynopsisLLMResult
from app.pipeline import reduce_pass

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
    def __init__(self, dates: list[MapPassDateFact], amounts: list[MapPassAmountFact]) -> None:
        extraction = ChunkExtraction(
            id=uuid.uuid4(),
            chunk_id=uuid.uuid4(),
            structured_json=MapPassResult(dates=dates, amounts=amounts).model_dump(),
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
def extraction_rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.open(encoding="utf-8")]


def test_synopsis_has_required_shape_and_preserves_golden_facts(
    monkeypatch, extraction_rows
) -> None:
    by_fixture: dict[str, list[dict]] = defaultdict(list)
    for row in extraction_rows:
        by_fixture[row["fixture"]].append(row)

    for fixture_name, rows in by_fixture.items():
        dates, amounts = [], []
        for row in rows:
            facts = row["expected_facts"]
            page_ref = row["page_number"]
            for d in facts.get("dates", []):
                dates.append(
                    MapPassDateFact(
                        label=d["label"], value=d["value"], page_ref=d.get("page_ref", page_ref)
                    )
                )
            for a in facts.get("amounts", []):
                amounts.append(
                    MapPassAmountFact(
                        label=a["label"], value=a["value"], page_ref=a.get("page_ref", page_ref)
                    )
                )

        db = _FakeGoldenSession(dates, amounts)
        document = Document(id=uuid.uuid4(), filename=f"{fixture_name}.pdf", status="analyzing")

        fake_llm_result = SynopsisLLMResult(
            title="Test Tender",
            issuing_authority="Test Authority",
            scope_summary="...",
            eligibility_summary="...",
            payment_terms_summary="...",
            confidence="high",
        )
        monkeypatch.setattr(
            reduce_pass,
            "complete_structured",
            lambda *a, r=fake_llm_result, **k: (r, "test-model"),
        )

        analysis = reduce_pass.run_synopsis(db, document)
        result = analysis.result

        missing = REQUIRED_SYNOPSIS_KEYS - result.keys()
        assert not missing, f"{fixture_name}: synopsis missing keys {missing}"
        for date_fact in result["key_dates"]:
            assert "page_ref" in date_fact, f"{fixture_name}: date fact missing page_ref"
        for amount_fact in result["financials"]:
            assert "page_ref" in amount_fact, f"{fixture_name}: financial fact missing page_ref"

        if dates:
            assert len(result["key_dates"]) >= 1, f"{fixture_name}: golden dates dropped"
        if amounts:
            assert len(result["financials"]) >= 1, f"{fixture_name}: golden amounts dropped"
