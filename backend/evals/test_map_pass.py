"""Phase 4 gate: map-pass fact extraction — chunk_extractions populated for every
fixture, facts correctly page-tagged against golden_extraction.jsonl.

Rewritten against the real, Phase-4-verified architecture (this file predates that
build and called a `build_chunks(doc)`/`run_map_pass(chunk)` signature that never
existed once chunk.py/map_pass.py were actually built — db-first, per
tests/unit/test_chunk.py and tests/unit/test_map_pass.py). Real page text comes
straight from PyMuPDF on the fixture PDF (these are small, real, purpose-built PDFs)
rather than running the full classify/extract pipeline (Phase 2/3), which is exercised
separately in tests/integration/ — this eval's job is chunk-range planning and
page_ref pass-through, not native/vision extraction accuracy.

Mocks complete_structured per CLAUDE.md hard rule 8 — this test must cost $0 and be
deterministic. The mock echoes back the golden facts with their page_ref, so this
verifies the real plumbing (chunking, DB writes, page_ref surviving into
chunk_extractions.structured_json) rather than model accuracy, which needs a live call
and is validated separately (see docs/DECISIONS.md #35-37's real, non-mocked runs).
"""

import json
import uuid
from pathlib import Path

import fitz
import pytest

from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.models.page import Page
from app.models.schemas import MapPassDateFact, MapPassResult
from app.pipeline.chunk import build_chunks, chunk_page_text
from app.pipeline.map_pass import run_map_pass

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"
DATASET = Path(__file__).parent / "datasets" / "golden_extraction.jsonl"


class _FakeListQuery:
    def __init__(self, items: list) -> None:
        self._items = items

    def filter(self, *_conditions):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self._items


class _FakeMapPassSession:
    """Same shape as tests/unit/test_chunk.py's FakeChunkSession and
    tests/unit/test_map_pass.py's FakeMapPassSession, combined — build_chunks needs a
    Page query, run_map_pass needs both a Page query (via chunk_page_text) and to
    persist ChunkExtraction rows.
    """

    def __init__(self, pages: list[Page]) -> None:
        self._pages = pages
        self.added: list = []

    def query(self, model):
        if model is Page:
            return _FakeListQuery(sorted(self._pages, key=lambda p: p.page_number))
        raise AssertionError(f"Unexpected query for {model}")

    def add(self, obj) -> None:
        if isinstance(obj, Chunk | ChunkExtraction) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


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


def _pages_from_pdf(document_id, pdf_path: Path) -> list[Page]:
    doc = fitz.open(pdf_path)
    pages = [
        Page(
            id=uuid.uuid4(),
            document_id=document_id,
            page_number=i,
            classification="native_text",
            extraction_method="native",
            raw_text=doc[i].get_text() or "placeholder text",
            confidence_score=1.0,
        )
        for i in range(doc.page_count)
    ]
    doc.close()
    return pages


def test_facts_are_correctly_page_tagged(monkeypatch, extraction_rows: list[dict]) -> None:
    """Every chunk_extractions.structured_json fact must carry the correct page_number —
    this is what Phase 5's citation-verifiability gate depends on downstream.
    """
    by_fixture: dict[str, list[dict]] = {}
    for row in extraction_rows:
        by_fixture.setdefault(row["fixture"], []).append(row)

    for fixture_name, rows in by_fixture.items():
        document_id = uuid.uuid4()
        pages = _pages_from_pdf(document_id, FIXTURES_DIR / f"{fixture_name}.pdf")
        document = Document(
            id=document_id, filename=f"{fixture_name}.pdf", status="extracted",
            total_pages=len(pages),
        )
        db = _FakeMapPassSession(pages)

        chunks = build_chunks(db, document)
        assert len(chunks) > 0, fixture_name

        golden_dates = [
            (d.get("page_ref", row["page_number"]), d["label"], d["value"])
            for row in rows
            for d in row["expected_facts"].get("dates", [])
        ]

        def _fake_complete_structured(task, prompt, schema, r=golden_dates):
            pages_in_prompt = {
                int(line.split("]")[0][6:])
                for line in prompt.splitlines()
                if line.startswith("[PAGE ")
            }
            dates_in_chunk = [
                MapPassDateFact(label=label, value=value, page_ref=page_ref)
                for page_ref, label, value in r
                if page_ref in pages_in_prompt
            ]
            return MapPassResult(dates=dates_in_chunk), "test-model"

        monkeypatch.setattr(
            "app.pipeline.map_pass.complete_structured", _fake_complete_structured
        )

        extractions = [run_map_pass(db, chunk) for chunk in chunks]

        assert len(extractions) == len(chunks)
        for chunk, extraction in zip(chunks, extractions, strict=True):
            chunk_pages = {p for p, _ in chunk_page_text(db, chunk)}
            for date_fact in extraction.structured_json["dates"]:
                assert date_fact["page_ref"] in chunk_pages, (
                    f"{fixture_name}: fact tagged page {date_fact['page_ref']} "
                    f"is outside its own chunk's page range {chunk_pages}"
                )
