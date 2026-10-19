"""Skip a map-pass LLM call for a chunk whose content has already been extracted —
closes the gap app.pipeline.dedupe's own docstring named but never built: that module
only ever recorded/counted a duplicate, never skipped the actual expensive work (the
map-pass LLM call, which runs once per ~25-page chunk, not once per page).

Content-hash keyed, same established pattern as dedupe.check_and_record/
fetch_links.get_cached_pages — but a distinct identity from either (docs/DECISIONS.md
#75's reasoning for ChunkExtractionCache being its own table, not a repurposed one):
"seen this exact chunk's content, here's its structured extraction."

The one correctness-critical piece: a cached MapPassResult's page_ref values were
computed against the ORIGINAL chunk's page numbers. The same content reappearing in a
different document, or later in the same document's global page sequence (e.g. a
tender's own content repeated as an attachment), sits at different page numbers.
remap_page_refs rewrites every page_ref onto the reusing chunk's real pages before
it's ever returned to a caller — never citing a page the current chunk doesn't
actually cover.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.chunk_extraction_cache import ChunkExtractionCache

logger = get_logger(__name__)

# Every field of MapPassResult that carries a page_ref (app/models/schemas.py:86-91) —
# kept here as the single place that must be updated if a 6th such field is ever added.
_PAGE_REF_LIST_FIELDS = ("dates", "amounts", "criteria", "risk_candidates", "documents_required")


def content_hash(pages: list[tuple[int, str]]) -> str:
    """Hashes the concatenated raw page texts, in page order — deliberately NOT the
    `[PAGE n]`-tagged rendering map_pass._format_chunk_content builds for the prompt.
    Hashing the tagged version would make identical content at different page numbers
    hash differently, defeating the entire point (mirrors how dedupe.py's own
    page-level content_hash already works: hash the raw text, not a page-numbered
    rendering of it).
    """
    joined = "\n\n".join(text for _, text in pages)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass
class CacheHit:
    structured_json: dict
    original_pages: list[int]
    model_used: str | None
    first_seen_chunk_id: uuid.UUID | None


def get_cached(db: Session, chash: str) -> CacheHit | None:
    """Returns the cached extraction for `chash` if one exists, incrementing its
    hit_count — mirrors fetch_links.get_cached_pages's exact lookup-and-increment
    pattern. None on a miss; callers then run the real LLM call and call store().
    """
    existing = db.get(ChunkExtractionCache, chash)
    if existing is None:
        return None
    existing.hit_count += 1
    existing.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return CacheHit(
        structured_json=existing.cached_structured_json,
        original_pages=existing.cached_original_pages,
        model_used=existing.cached_model_used,
        first_seen_chunk_id=existing.first_seen_chunk_id,
    )


def store(
    db: Session,
    chash: str,
    structured_json: dict,
    original_pages: list[int],
    model_used: str | None,
    chunk_id: uuid.UUID,
) -> None:
    """Seeds the cache after a genuine miss + a completed LLM call — only ever called
    once per chash (get_cached already returned None for this hash in the same
    run_map_pass call), so no upsert-race handling needed, mirroring
    dedupe.check_and_record's plain-insert pattern.
    """
    row = ChunkExtractionCache(
        content_hash=chash,
        cached_structured_json=structured_json,
        cached_original_pages=original_pages,
        cached_model_used=model_used,
        first_seen_chunk_id=chunk_id,
        hit_count=0,
    )
    db.add(row)
    db.commit()


def remap_page_refs(
    structured_json: dict, original_pages: list[int], current_pages: list[int]
) -> dict:
    """Rewrites every page_ref in `structured_json` from `original_pages`' sequence
    onto `current_pages`' sequence, position-for-position. Always well-defined: if the
    content hash matched, the two chunks have the exact same page count and text in
    the exact same order, by construction — len(original_pages) == len(current_pages)
    is a precondition this relies on, not defensively checked against malformed input.

    Pure function, no I/O — CLAUDE.md hard rule 3 (citation-affecting logic is code,
    never left to the model or assumed correct without rewriting).
    """
    position_by_original_page = {page: i for i, page in enumerate(original_pages)}
    remapped = dict(structured_json)
    for field in _PAGE_REF_LIST_FIELDS:
        items = remapped.get(field) or []
        remapped_items = []
        for item in items:
            position = position_by_original_page.get(item["page_ref"])
            if position is None:
                # The model cited a page outside this chunk's own range — already
                # possible today in the non-cached path too (nothing validates
                # page_ref against the chunk's actual pages beyond Pydantic's `ge=0`).
                # Pass it through unchanged rather than crash; this is no worse than
                # today's behavior, just now visible instead of silent.
                logger.warning(
                    "map_pass_cache.page_ref_outside_original_range",
                    field=field,
                    page_ref=item["page_ref"],
                    original_pages=original_pages,
                )
                remapped_items.append(item)
            else:
                remapped_items.append({**item, "page_ref": current_pages[position]})
        remapped[field] = remapped_items
    return remapped
