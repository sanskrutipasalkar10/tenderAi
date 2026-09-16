"""Cross-document boilerplate dedupe — checked after a page's text is extracted
(native or vision), keyed on the same `content_hash` stored on `pages` (docs/SPEC.md
§2.1 stage 2: "content hash checked against boilerplate_cache before extraction is
trusted as 'new work'"). Not scoped to one document — a repeated clause across
different tenders from the same or different issuing authorities is still a hit.

Phase 3 scope: records and counts duplicates (the spec's own MVP success criterion —
"a second, near-duplicate tender... visibly reuses cached extraction... verify via
boilerplate_cache.hit_count"). `cached_extraction` stores the raw text for now (a
useful Phase 3 placeholder — a future page with this exact hash could reuse it without
re-running vision at all); once Phase 4 exists, this becomes the real optimization
target (skip re-running the map-pass LLM call on a chunk of already-seen boilerplate).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.boilerplate_cache import BoilerplateCache


def check_and_record(
    db: Session,
    content_hash: str,
    document_id: uuid.UUID,
    raw_text: str,
    issuing_authority: str | None = None,
) -> bool:
    """Checks whether `content_hash` has been seen before; records it either way.

    Returns True on a cache hit (hit_count incremented on an existing row), False if
    this is the first time this exact content has been seen (a new row is created).
    """
    existing = db.get(BoilerplateCache, content_hash)
    if existing is not None:
        existing.hit_count += 1
        existing.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return True

    row = BoilerplateCache(
        content_hash=content_hash,
        issuing_authority=issuing_authority,
        cached_extraction={"raw_text": raw_text},
        first_seen_document_id=document_id,
        hit_count=0,
    )
    db.add(row)
    db.commit()
    return False


def hit_count(db: Session) -> int:
    """Total hits recorded across all boilerplate_cache rows — used by the adversarial
    eval (golden_adversarial.jsonl's "boilerplate_duplicate" case) to assert the count
    increments on a near-duplicate upload.
    """
    total = 0
    for row in db.query(BoilerplateCache).all():
        total += row.hit_count
    return total
