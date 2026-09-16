"""Chunk assembly — groups a document's pages into overlapping windows for the map
pass (docs/SPEC.md §2.1 stage 3). Page-range math and token counting are plain code,
never a prompt instruction (CLAUDE.md hard rule 3).

Chunk size is deliberately much smaller than the spec's own starting suggestion
("~20-30 page chunks"), based on real measurement, not guesswork: a real 25-page chunk
(~17K tokens) with the actual map-pass extraction prompt did not complete even once in
repeated attempts up to an 8-minute timeout against gpt-oss:20b-cloud (docs/DECISIONS.md
#35) — this is a real model-throughput ceiling for this task's complexity (a long,
4-category structured-extraction instruction plus strict JSON output), not a tunable
knob to push further. A 3-page/~2K-token chunk completed in 79s. 5 pages is a
deliberately conservative middle ground pending a fuller latency sweep.
"""

from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.page import Page

CHUNK_SIZE_PAGES = 5
CHUNK_OVERLAP_PAGES = 1

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


def build_chunks(db: Session, document: Document) -> list[Chunk]:
    """Creates and persists Chunk rows for every page range of `document`, per
    plan_chunk_ranges. Called once, after extraction (Phase 2/3) is complete for the
    whole document — chunking needs every page's raw_text to compute token counts.
    """
    pages = (
        db.query(Page)
        .filter(Page.document_id == document.id)
        .order_by(Page.page_number)
        .all()
    )
    pages_by_number = {p.page_number: p for p in pages}
    total_pages = document.total_pages or len(pages)

    chunk_rows = []
    for start_page, end_page in plan_chunk_ranges(total_pages):
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
