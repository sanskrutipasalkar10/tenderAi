"""Adds chunk_extraction_cache (content-hash keyed, mirrors boilerplate_cache's and
linked_document_cache's established shape, docs/DECISIONS.md #75's reasoning for a
new table per distinct identity) and chunk_extractions.reused_from_chunk_id.

Closes a real, previously-acknowledged gap: app/pipeline/dedupe.py's own docstring
said outright that duplicate content was only ever recorded/counted, never used to
skip the actual expensive work (the map-pass LLM call, which runs once per ~25-page
chunk). This is that: an identical chunk (same page text, same order, regardless of
which document or which page numbers it appears at) reuses the prior structured
extraction instead of paying for another LLM call.

cached_original_pages (the ordered page_number list the cached extraction was first
computed against) is required, not optional — app.pipeline.map_pass_cache.
remap_page_refs needs it to rewrite every cached page_ref onto the CURRENT chunk's
real page numbers before reuse. Skipping this would silently point citations at the
wrong page, which this project treats as non-negotiable (CLAUDE.md hard rule 4/6).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DDL = """
CREATE TABLE IF NOT EXISTS chunk_extraction_cache (
    content_hash TEXT PRIMARY KEY,
    cached_structured_json JSONB NOT NULL,
    cached_original_pages JSONB NOT NULL,
    cached_model_used TEXT,
    first_seen_chunk_id UUID REFERENCES chunks(id),
    hit_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
ALTER TABLE chunk_extractions ADD COLUMN IF NOT EXISTS reused_from_chunk_id UUID REFERENCES chunks(id);
"""

DROP_ALL = """
ALTER TABLE chunk_extractions DROP COLUMN IF EXISTS reused_from_chunk_id;
DROP TABLE IF EXISTS chunk_extraction_cache;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP_ALL)
