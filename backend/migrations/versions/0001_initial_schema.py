"""Initial schema — applied verbatim from docs/SPEC.md / tender-ai-platform-implementation-spec section 3.1.
Do not redesign this schema in a later migration without a DECISIONS.md entry.

Revision ID: 0001
Revises:
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DDL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE company_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name        TEXT NOT NULL,
    annual_turnover      JSONB,
    certifications       JSONB,
    past_projects        JSONB,
    geographic_presence  JSONB,
    sectors               JSONB,
    max_capacity_pct     NUMERIC,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename            TEXT NOT NULL,
    issuing_authority    TEXT,
    total_pages          INTEGER,
    status               TEXT NOT NULL DEFAULT 'uploaded'
                          CHECK (status IN ('uploaded','classifying','extracting','extracted','analyzing','ready','failed')),
    original_pdf_s3_key  TEXT,
    company_profile_id   UUID REFERENCES company_profiles(id),
    uploaded_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number         INTEGER NOT NULL,
    classification      TEXT NOT NULL
                          CHECK (classification IN ('native_text','scanned_image','table','mixed')),
    extraction_method    TEXT
                          CHECK (extraction_method IN ('native','vision_cloud','vision_local')),
    raw_text            TEXT,
    content_hash        CHAR(64),
    image_s3_key         TEXT,
    confidence_score     NUMERIC,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_number)
);

CREATE TABLE extracted_tables (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id             UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    table_type           TEXT,
    table_data           JSONB NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE boilerplate_cache (
    content_hash          CHAR(64) PRIMARY KEY,
    issuing_authority      TEXT,
    cached_extraction      JSONB,
    first_seen_document_id UUID REFERENCES documents(id),
    hit_count              INTEGER NOT NULL DEFAULT 0,
    last_used_at           TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    start_page          INTEGER NOT NULL,
    end_page            INTEGER NOT NULL,
    token_count          INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunk_extractions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id            UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    structured_json      JSONB NOT NULL,
    model_used           TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document_analysis (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    module               TEXT NOT NULL
                          CHECK (module IN ('go_no_go','synopsis','risk_finder')),
    result                JSONB NOT NULL,
    model_used            TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, module)
);

CREATE INDEX idx_pages_document_page   ON pages (document_id, page_number);
CREATE INDEX idx_pages_content_hash    ON pages (content_hash);
CREATE INDEX idx_chunks_document       ON chunks (document_id);
CREATE INDEX idx_chunk_extractions_chunk ON chunk_extractions (chunk_id);
CREATE INDEX idx_document_analysis_doc ON document_analysis (document_id);
"""

DROP_ALL = """
DROP TABLE IF EXISTS document_analysis;
DROP TABLE IF EXISTS chunk_extractions;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS boilerplate_cache;
DROP TABLE IF EXISTS extracted_tables;
DROP TABLE IF EXISTS pages;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS company_profiles;
"""


def upgrade() -> None:
    bind = op.get_bind()
    try:
        with bind.begin_nested():
            bind.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "vector"'))
    except Exception:
        # pgvector isn't installed on every Postgres instance (confirmed absent from
        # pg_available_extensions on the shared dev instance) and no MVP table/column
        # uses it — see docs/SPEC.md §2.7. Non-fatal: enable it for real once a feature
        # actually needs it, per docs/DECISIONS.md.
        print(
            "WARNING: 'vector' extension unavailable on this Postgres instance — "
            "skipped. No MVP table uses it; see docs/SPEC.md §2.7."
        )
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP_ALL)
