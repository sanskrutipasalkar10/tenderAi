"""Supporting documents attached to a tender at upload time (upload-time-only scope,
confirmed with the user — not a general "attach anytime" flow, which would need a real
re-analysis trigger that doesn't exist yet). Mirrors the existing GeM-linked-document
pattern (migration 0004, docs/DECISIONS.md #75) rather than inventing a new mechanism:
a supporting document (a company certificate, a past-project reference, a clarification
doc) becomes more `pages` rows on the SAME document_id, continuing the page_number
sequence — real tender-relevant content, not a lesser source, so it flows through the
identical classify/extract/chunk/map/reduce pipeline and gets real page citations like
every other page. This project has no retrieval step (CLAUDE.md) — attachments are read
in full, not indexed for lookup.

  - `document_attachments` — one row per uploaded supporting file (filename + S3 key).
    A separate table rather than a JSONB column on `documents`, matching this project's
    existing relational style for anything queried/joined against (`extracted_tables`,
    `linked_document_cache`), not just stored and redisplayed whole.

  - `pages.attachment_id` — nullable FK to `document_attachments`. NULL for the
    uploaded PDF's own pages and for hyperlink-fetched pages (those keep using the
    existing `source_url`); set for a page that came from a manually-attached
    supporting document. Deliberately a separate column from `source_url` rather than
    a synthetic "attachment://" URL squeezed into it — reusing `source_url` for a local
    upload with no real URL would conflate two different provenances into one field
    (CLAUDE.md: explicit over clever).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DDL = """
CREATE TABLE IF NOT EXISTS document_attachments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    s3_key        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE pages ADD COLUMN IF NOT EXISTS attachment_id UUID
    REFERENCES document_attachments(id) ON DELETE SET NULL;
"""

DROP_ALL = """
ALTER TABLE pages DROP COLUMN IF EXISTS attachment_id;
DROP TABLE IF EXISTS document_attachments;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP_ALL)
