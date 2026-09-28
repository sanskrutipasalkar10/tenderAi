"""Chunk assembly — groups a document's pages into overlapping windows for the map
pass (docs/SPEC.md §2.1 stage 3). Page-range math and token counting are plain code,
never a prompt instruction (CLAUDE.md hard rule 3).

CHUNK_SIZE_PAGES was 5 for most of this project's history — deliberately much smaller
than the spec's own starting suggestion ("~20-30 page chunks"), because a real 25-page
chunk (~17K tokens) never completed even once against gpt-oss:20b-cloud (Ollama Cloud)
up to an 8-minute timeout (docs/DECISIONS.md #35) — a real model-throughput ceiling,
not a tunable knob.

That ceiling is gone now that Gemini is primary (docs/DECISIONS.md #76) — Gemini 3.8
Flash has a 1M-token context window, so this reverts toward the spec's own original
25-page suggestion rather than staying capped by a constraint that no longer applies.
Verified empirically before committing to this, not just assumed (docs/DECISIONS.md
#77) — real map-pass runs against a real, saved 25-page tender annexure, checking
specifically for a "lost in the middle" failure (facts from deep-middle pages getting
dropped while beginning/end pages are captured, a documented LLM behavior over long
contexts): two separate runs both correctly extracted real, page-tagged facts from the
literal first page, deep-middle pages (12-16 — multiple distinct risk clauses each
correctly attributed), and the literal last page of the range. No systematic
middle-dropping observed. CHUNK_OVERLAP_PAGES bumped from 1 to 2 alongside this — not
because overlap needs to scale with chunk size (a single clause rarely spans more than
a page or two, whatever the window size), but as a modest safety margin for the now
much-less-frequent chunk boundaries.
"""

from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.page import Page

CHUNK_SIZE_PAGES = 25
CHUNK_OVERLAP_PAGES = 2

# ~4 characters/token is the standard rough estimate for English text — close enough
# for chunk-sizing purposes (deciding how much text a map-pass call is about to send),
# not exact provider-token accounting. Deliberately not tiktoken: it fetches its BPE
# file over the network on first use (real, observed multi-minute hang the first time
# this ran), an unnecessary and non-deterministic dependency for a rough estimate —
# see docs/DECISIONS.md #33.
_CHARS_PER_TOKEN_ESTIMATE = 4


def _count_tokens(text: str | None) -> int:
    if not text:
        return 0
    return len(text) // _CHARS_PER_TOKEN_ESTIMATE


def plan_chunk_ranges(
    total_pages: int,
    chunk_size: int = CHUNK_SIZE_PAGES,
    overlap: int = CHUNK_OVERLAP_PAGES,
) -> list[tuple[int, int]]:
    """Returns (start_page, end_page) tuples, 0-indexed inclusive, covering every page
    from 0 to total_pages-1 with `overlap` pages of overlap between consecutive chunks.
    Pure function — no I/O, easy to unit test and to re-tune independently of the
    DB-writing half below.
    """
    if total_pages <= 0:
        return []

    ranges: list[tuple[int, int]] = []
    start = 0
    while start < total_pages:
        end = min(start + chunk_size - 1, total_pages - 1)
        ranges.append((start, end))
        if end == total_pages - 1:
            break
        start = end + 1 - overlap
    return ranges


def _source_spans(pages: list[Page]) -> list[tuple[int, int]]:
    """Groups `pages` (already ordered by page_number) into (start_page, end_page)
    spans sharing the same source_url — a run of pages with source_url=None is the
    uploaded PDF's own pages; each hyperlinked document fetched by
    app.pipeline.fetch_links forms its own span, appended after (docs/DECISIONS.md).
    For a document with no linked pages this always returns exactly one span covering
    every page, identical to treating the whole document as one range.
    """
    if not pages:
        return []
    spans: list[tuple[int, int]] = []
    span_start = pages[0].page_number
    current_source = pages[0].source_url
    prev_number = pages[0].page_number
    for p in pages[1:]:
        if p.source_url != current_source:
            spans.append((span_start, prev_number))
            span_start = p.page_number
            current_source = p.source_url
        prev_number = p.page_number
    spans.append((span_start, prev_number))
    return spans


def build_chunks(db: Session, document: Document) -> list[Chunk]:
    """Creates and persists Chunk rows for every page range of `document`, per
    plan_chunk_ranges — called once per source span (_source_spans above), not once
    over the whole document, so a chunk window never straddles the boundary between
    the uploaded PDF's own pages and a hyperlinked document's pages (docs/DECISIONS.md
    — mixing unrelated content into one map-pass call with no signal to the model
    would otherwise be possible once page_number can span multiple real sources).
    Called once, after extraction (Phase 2/3) is complete for the whole document —
    chunking needs every page's raw_text to compute token counts.
    """
    pages = (
        db.query(Page)
        .filter(Page.document_id == document.id)
        .order_by(Page.page_number)
        .all()
    )
    pages_by_number = {p.page_number: p for p in pages}

    chunk_rows = []
    for span_start, span_end in _source_spans(pages):
        span_length = span_end - span_start + 1
        for local_start, local_end in plan_chunk_ranges(span_length):
            start_page = span_start + local_start
            end_page = span_start + local_end
            token_count = sum(
                _count_tokens(pages_by_number[n].raw_text)
                for n in range(start_page, end_page + 1)
                if n in pages_by_number
            )
            chunk = Chunk(
                document_id=document.id,
                start_page=start_page,
                end_page=end_page,
                token_count=token_count,
            )
            db.add(chunk)
            chunk_rows.append(chunk)

    db.commit()
    for chunk in chunk_rows:
        db.refresh(chunk)
    return chunk_rows


def chunk_page_text(db: Session, chunk: Chunk) -> list[tuple[int, str]]:
    """Returns [(page_number, raw_text), ...] for every page in `chunk`'s range that
    has extracted text — pages with no text (a failed extraction) are omitted here,
    not fabricated as empty content for the map pass to reason about.
    """
    pages = (
        db.query(Page)
        .filter(
            Page.document_id == chunk.document_id,
            Page.page_number >= chunk.start_page,
            Page.page_number <= chunk.end_page,
            Page.raw_text.isnot(None),
        )
        .order_by(Page.page_number)
        .all()
    )
    # The isnot(None) filter above guarantees raw_text is populated; mypy can't infer
    # that from the ORM's `str | None` column type alone.
    return [(p.page_number, p.raw_text) for p in pages if p.raw_text is not None]
