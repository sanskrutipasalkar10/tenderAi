"""Unit tests for scripts.report_cost — no real DB/LLM, per CLAUDE.md hard rule 8.
Pure arithmetic over fake chunk/extraction data, same FakeListQuery pattern used by
tests/unit/test_reduce_pass.py.
"""

import uuid

from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.models.schemas import MapPassCriterionFact, MapPassResult
from scripts.report_cost import report_for_document


class _FakeListQuery:
    def __init__(self, items: list) -> None:
        self._items = items

    def filter(self, *_conditions):
        return self

    def all(self):
        return self._items


class _FakeReportSession:
    def __init__(self, chunks: list[Chunk], extractions: list[ChunkExtraction]) -> None:
        self._chunks = chunks
        self._extractions = extractions

    def query(self, model):
        if model is Chunk:
            return _FakeListQuery(self._chunks)
        if model is ChunkExtraction:
            return _FakeListQuery(self._extractions)
        raise AssertionError(f"Unexpected query for {model}")


def test_map_pass_tokens_reflect_every_built_chunk_not_just_completed_ones() -> None:
    document = Document(id=uuid.uuid4(), filename="x.pdf", status="extracted", total_pages=10)
    chunks = [
        Chunk(id=uuid.uuid4(), document_id=document.id, start_page=0, end_page=4, token_count=100),
        Chunk(id=uuid.uuid4(), document_id=document.id, start_page=4, end_page=8, token_count=150),
    ]
    # Only the first chunk has actually been map-passed.
    extractions = [
        ChunkExtraction(
            id=uuid.uuid4(), chunk_id=chunks[0].id, structured_json=MapPassResult().model_dump()
        )
    ]
    db = _FakeReportSession(chunks, extractions)

    report = report_for_document(db, document)

    assert report["chunks"] == 2
    assert report["map_pass_tokens_projected"] == 250  # both chunks' tokens, regardless
    assert report["map_pass_calls_projected"] == 2
    assert report["map_pass_calls_completed"] == 1
    assert report["required_spend_usd"] == 0


def test_reduce_pass_tokens_only_come_from_completed_extractions() -> None:
    document = Document(id=uuid.uuid4(), filename="x.pdf", status="extracted", total_pages=5)
    chunk = Chunk(id=uuid.uuid4(), document_id=document.id, start_page=0, end_page=4)
    extraction = ChunkExtraction(
        id=uuid.uuid4(),
        chunk_id=chunk.id,
        structured_json=MapPassResult(
            criteria=[MapPassCriterionFact(description="Min turnover 50 Cr", page_ref=1)]
        ).model_dump(),
    )
    db = _FakeReportSession([chunk], [extraction])

    report = report_for_document(db, document)

    assert report["reduce_pass_calls_from_completed_chunks"] >= 1
    assert report["reduce_pass_tokens_from_completed_chunks"] > 0


def test_document_with_no_chunks_reports_zero_everything() -> None:
    document = Document(id=uuid.uuid4(), filename="x.pdf", status="uploaded", total_pages=None)
    db = _FakeReportSession([], [])

    report = report_for_document(db, document)

    assert report["chunks"] == 0
    assert report["map_pass_tokens_projected"] == 0
    assert report["reduce_pass_tokens_from_completed_chunks"] == 0
