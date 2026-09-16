import uuid

import pytest

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.page import Page
from app.pipeline.chunk import (
    build_chunks,
    chunk_page_text,
    plan_chunk_ranges,
)


class FakeChunkSession:
    """Minimal fake supporting the query/add/commit/refresh calls chunk.py makes."""

    def __init__(self, pages: list[Page]) -> None:
        self._pages = pages
        self.added: list[Chunk] = []

    def query(self, model):
        if model is Page:
            return _FakePageQuery(self._pages)
        raise AssertionError(f"Unexpected query for {model}")

    def add(self, obj) -> None:
        if isinstance(obj, Chunk) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


class _FakePageQuery:
    def __init__(self, pages: list[Page]) -> None:
        self._pages = pages
        self._filters: list = []

    def filter(self, *conditions):
        self._filters.extend(conditions)
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        # The fake doesn't interpret SQLAlchemy filter expressions — the tests below
        # only ever construct one document's worth of pages per session, so "all
        # pages passed to the fake" is already the correct filtered set.
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


# --- plan_chunk_ranges: pure function, no DB -----------------------------------------


def test_single_chunk_when_document_fits_in_one() -> None:
    assert plan_chunk_ranges(6, chunk_size=25, overlap=2) == [(0, 5)]


def test_zero_pages_yields_no_chunks() -> None:
    assert plan_chunk_ranges(0) == []


def test_multi_chunk_covers_every_page_with_correct_overlap() -> None:
    ranges = plan_chunk_ranges(50, chunk_size=25, overlap=2)

    # every page 0..49 covered by at least one chunk
    covered = set()
    for start, end in ranges:
        covered.update(range(start, end + 1))
    assert covered == set(range(50))

    # consecutive chunks overlap by exactly `overlap` pages
    for (s1, e1), (s2, e2) in zip(ranges, ranges[1:], strict=False):
        overlap_pages = set(range(s1, e1 + 1)) & set(range(s2, e2 + 1))
        assert len(overlap_pages) == 2

    # last chunk ends exactly at the last page — no dangling range past the document
    assert ranges[-1][1] == 49


def test_exact_multiple_of_chunk_size_has_no_trailing_empty_chunk() -> None:
    ranges = plan_chunk_ranges(25, chunk_size=25, overlap=2)
    assert ranges == [(0, 24)]


@pytest.mark.parametrize("total_pages", [1, 5, 24, 25, 26, 100, 372])
def test_ranges_always_fully_cover_document_no_gaps(total_pages: int) -> None:
    ranges = plan_chunk_ranges(total_pages, chunk_size=25, overlap=2)
    covered = set()
    for start, end in ranges:
        covered.update(range(start, end + 1))
    assert covered == set(range(total_pages))


# --- build_chunks / chunk_page_text: need a (fake) DB ---------------------------------


def test_build_chunks_creates_rows_with_token_counts() -> None:
    # 4 pages fits inside one chunk at the current default CHUNK_SIZE_PAGES (5, see
    # docs/DECISIONS.md #35) — this test is about token-count correctness, not chunk
    # count, so it deliberately stays under whatever the current default is rather
    # than hardcoding a page count that assumes a specific default.
    from app.pipeline.chunk import CHUNK_SIZE_PAGES

    document_id = uuid.uuid4()
    total_pages = min(4, CHUNK_SIZE_PAGES)
    document = Document(
        id=document_id, filename="x.pdf", status="extracted", total_pages=total_pages
    )
    pages = [_make_page(document_id, i, f"page {i} text " * 20) for i in range(total_pages)]
    db = FakeChunkSession(pages)

    chunks = build_chunks(db, document)

    assert len(chunks) == 1
    assert chunks[0].start_page == 0
    assert chunks[0].end_page == total_pages - 1
    assert chunks[0].token_count > 0


def test_build_chunks_skips_pages_with_no_text_for_token_counting() -> None:
    document_id = uuid.uuid4()
    document = Document(id=document_id, filename="x.pdf", status="extracted", total_pages=3)
    pages = [
        _make_page(document_id, 0, "real text here"),
        _make_page(document_id, 1, None),  # failed extraction
        _make_page(document_id, 2, "more real text"),
    ]
    db = FakeChunkSession(pages)

    chunks = build_chunks(db, document)

    assert len(chunks) == 1
    assert chunks[0].token_count > 0  # counted the 2 pages with text, skipped the None


def test_chunk_page_text_returns_page_number_text_pairs_in_order() -> None:
    # The fake's query.all() can't faithfully interpret a real SQLAlchemy
    # `raw_text.isnot(None)` filter expression, so this fake's page list is
    # pre-filtered to only the pages a real query would return — the actual
    # None-filtering behavior is verified against real Postgres by
    # tests/integration/test_ingestion_integration.py's classification/extraction
    # assertions and, once map_pass.py exists, evals/test_map_pass.py.
    document_id = uuid.uuid4()
    pages = [_make_page(document_id, 0, "alpha"), _make_page(document_id, 2, "gamma")]
    db = FakeChunkSession(pages)
    chunk = Chunk(document_id=document_id, start_page=0, end_page=2, token_count=10)

    result = chunk_page_text(db, chunk)

    assert result == [(0, "alpha"), (2, "gamma")]
