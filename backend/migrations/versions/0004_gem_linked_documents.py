"""GeM tender cover sheets link out to the real tender content instead of embedding it
(confirmed against 3 real GeM-Bidding-*.pdf files — a cover sheet literally says
"TERMS AND CONDITIONS AND SCOPE OF WORK AS PER ANNEXURE A ENCLOSED" where Annexure A is
a clickable URI, not an attachment; `doc.embfile_count() == 0` on all three). This adds:

  - `pages.source_url` — NULL for a page from the uploaded PDF itself, set to the
    origin URL for a page fetched from a hyperlink. Chosen over a separate
    parent/child Document relationship (docs/DECISIONS.md) — one Document row per
    tender, linked-doc content becomes more `pages` rows on the same document_id,
    continuing the page_number sequence past the cover PDF's own page count (required
    by pages' existing UNIQUE(document_id, page_number)).

  - `linked_document_cache` — caches a fetched-and-extracted linked document by URL
    identity, for the GeM links that are boilerplate reused across many different
    tenders (General Terms & Conditions, "list of categories where trials are
    allowed", etc.) so they're fetched once, not once per tender. Deliberately a new
    table rather than repurposing `boilerplate_cache` — that table's `content_hash` PK
    means "seen this exact text before" (a different identity than "already fetched
    this URL"); see docs/DECISIONS.md.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-24

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DDL = """
ALTER TABLE pages ADD COLUMN IF NOT EXISTS source_url TEXT;

CREATE TABLE IF NOT EXISTS linked_document_cache (
    url_hash                CHAR(64) PRIMARY KEY,
    source_url              TEXT NOT NULL,
    cached_extraction       JSONB,
    first_seen_document_id  UUID REFERENCES documents(id),
    hit_count                INTEGER NOT NULL DEFAULT 0,
    last_used_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

DROP_ALL = """
DROP TABLE IF EXISTS linked_document_cache;
ALTER TABLE pages DROP COLUMN IF EXISTS source_url;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP_ALL)
