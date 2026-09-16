"""Unit tests for app.pipeline.map_pass — LLM call mocked at complete_structured, per
CLAUDE.md hard rule 8. Real map-pass accuracy against a golden dataset belongs in
evals/test_map_pass.py once that eval's own mocking (or deliberate real-call mode) is
wired up for Phase 4/5's gate.
"""

import uuid

from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.page import Page
from app.models.schemas import MapPassAmountFact, MapPassDateFact, MapPassResult
from app.pipeline import map_pass


class FakeMapPassSession:
    def __init__(self, pages: list[Page]) -> None:
        self._pages = pages
        self.added: list = []

    def query(self, model):
        if model is Page:
            return _FakePageQuery(self._pages)
        raise AssertionError(f"Unexpected query for {model}")

    def add(self, obj) -> None:
        if isinstance(obj, ChunkExtraction) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


class _FakePageQuery:
    def __init__(self, pages: list[Page]) -> None:
        self._pages = pages

    def filter(self, *_conditions):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return sorted(self._pages, key=lambda p: p.page_number)


def _make_page(document_id, page_number, raw_text) -> Page:
    return Page(
        id=uuid.uuid4(),
        document_id=document_id,
        page_number=page_number,
        classification="native_text",
        extraction_method="native",
        raw_text=raw_text,
        content_hash="hash" if raw_text else None,
        confidence_score=1.0 if raw_text else 0.0,
    )


def test_format_chunk_content_tags_every_page() -> None:
    content = map_pass._format_chunk_content([(0, "first page text"), (1, "second page text")])
    assert "[PAGE 0]" in content
    assert "first page text" in content
    assert "[PAGE 1]" in content
    assert "second page text" in content


def test_empty_chunk_produces_extraction_without_llm_call(monkeypatch) -> None:
    document_id = uuid.uuid4()
    chunk = Chunk(id=uuid.uuid4(), document_id=document_id, start_page=0, end_page=2, token_count=0)
    db = FakeMapPassSession(pages=[])  # no pages with text at all

    called = False

    def _should_not_be_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("complete_structured must not be called for an empty chunk")

    monkeypatch.setattr(map_pass, "complete_structured", _should_not_be_called)

    extraction = map_pass.run_map_pass(db, chunk)

    assert called is False
    assert extraction.structured_json == MapPassResult().model_dump()
    assert extraction.model_used is None


def test_successful_map_pass_persists_structured_facts(monkeypatch) -> None:
    document_id = uuid.uuid4()
    pages = [_make_page(document_id, 0, "Bid submission deadline: 15 Nov 2026")]
    db = FakeMapPassSession(pages)
    chunk = Chunk(
        id=uuid.uuid4(), document_id=document_id, start_page=0, end_page=0, token_count=10
    )

    fake_result = MapPassResult(
        dates=[MapPassDateFact(label="Bid submission deadline", value="15 Nov 2026", page_ref=0)],
        amounts=[MapPassAmountFact(label="EMD", value="INR 50 Lakh", page_ref=0)],
    )
    monkeypatch.setattr(
        map_pass,
        "complete_structured",
        lambda task, prompt, schema: (fake_result, "ollama_chat/gpt-oss:20b-cloud"),
    )

    extraction = map_pass.run_map_pass(db, chunk)

    assert extraction.chunk_id == chunk.id
    assert extraction.model_used == "ollama_chat/gpt-oss:20b-cloud"
    assert extraction.structured_json["dates"][0]["page_ref"] == 0
    assert extraction.structured_json["amounts"][0]["value"] == "INR 50 Lakh"
    assert extraction in db.added


def test_run_map_pass_for_document_processes_every_chunk_independently(monkeypatch) -> None:
    document_id = uuid.uuid4()
    pages = [_make_page(document_id, i, f"text {i}") for i in range(3)]
    db = FakeMapPassSession(pages)
    chunks = [
        Chunk(id=uuid.uuid4(), document_id=document_id, start_page=0, end_page=1, token_count=5),
        Chunk(id=uuid.uuid4(), document_id=document_id, start_page=1, end_page=2, token_count=5),
    ]

    call_count = 0

    def _fake_complete(task, prompt, schema):
        nonlocal call_count
        call_count += 1
        return MapPassResult(), "ollama_chat/gpt-oss:20b-cloud"

    monkeypatch.setattr(map_pass, "complete_structured", _fake_complete)

    extractions = map_pass.run_map_pass_for_document(db, chunks)

    assert len(extractions) == 2
    assert call_count == 2
