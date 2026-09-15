# Tender AI Platform — Implementation Spec

Internal reference for implementation. Sections: (1) project overview, (2) architecture & setup, (3) database structure.

---

## 1. Project overview

### What we're building

An AI system that reads Indian government tender PDFs (50–1000+ pages, mixed native text, scanned images, and tables) and produces three outputs per tender:

1. **Go/No-Go Analyzer** — scores the tender against a company's profile (turnover, certifications, past projects) and recommends Go / No-Go / Conditional-Go with reasoning.
2. **AI Tender Synopsis** — condenses the full document into a structured, 5-minute-read summary (title, dates, financial figures, scope, eligibility, payment terms).
3. **AI Risk Finder** — scans every clause for risky or one-sided terms (liquidated damages, indemnity, termination, payment terms) and returns a ranked, page-cited risk list.

### Why this exists

Bid teams currently spend 3–7 days manually reading a single tender before deciding whether to bid. The platform compresses that to minutes, without dropping accuracy — every AI-generated risk flag must be traceable back to the exact page it came from.

### Goals

- Correctly extract text from **any** page type — native digital text, scanned/faxed images, and tables — with nothing silently dropped or garbled.
- Never miss a clause due to document length. Completeness matters more than speed; a 1000-page document must be read in full, not sampled.
- Every AI claim (especially risk flags) must cite a page number and be verifiable against the original document.
- Never re-do expensive work: repeated boilerplate clauses across tenders should be recognized and skipped, and a finished analysis should never be recomputed for the same tender.
- Start on free-tier / local models — no required paid API spend for the MVP.

### Non-goals for MVP (explicitly out of scope for now)

- Auto-fetching tenders from GeM/CPPP/state portals (user uploads the PDF manually).
- Multi-tenant / multi-organization support.
- BOQ cost estimation or auto-filling tender forms.
- A chat/Q&A interface over a tender (this is a later, separate feature — see Section 2, "future: vector index").

### Success criteria (MVP demo)

- Upload a real tender PDF (mixed text/scan/table) and get all three module outputs back correctly, each risk flag citing a real page.
- A second, near-duplicate tender from the same issuing authority visibly reuses cached extraction for repeated boilerplate (verify via `boilerplate_cache.hit_count`).
- Re-opening an already-analyzed tender returns instantly from storage, no re-processing.

---

## 2. Architecture & setup

### 2.1 Pipeline stages

```
1. Ingestion & classification
   PDF upload → per-page classifier (native_text / scanned_image / table / mixed)
   → native pages: direct text extraction (free)
   → scanned pages: render to image → vision model → text
   → table pages: render to image → vision model → markdown table text
   → all pages converge as plain text, tagged with page_number + confidence

2. Storage
   → text + metadata → PostgreSQL
   → original PDF + page images → object storage (S3-compatible)
   → content hash checked against boilerplate_cache before extraction is trusted as "new work"

3. Chunking & two-pass AI
   → pages grouped into ~20–30 page overlapping chunks
   → Map pass (cheap/fast model): per chunk, extract facts (dates, amounts, candidate risks) as JSON, each tagged with page number
   → Reduce pass (strongest model): merge all chunk outputs + company profile → final judgment per module (score / synopsis / risk list)

4. Serving
   → results read directly from document_analysis table (no recomputation)
   → high-severity risk flags re-verified against the original page in the raw layer before display
```

### 2.2 Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Native PDF parsing | `PyMuPDF` (fitz), `pdfplumber` | Page classification signals + native text extraction |
| Table extraction (native tables) | `pdfplumber`, `Camelot` | For tables with a native text layer |
| Vision extraction (scanned/table images) | Gemini API (free tier) primary; `qwen2.5vl:7b` via Ollama for offline/private work | See Section 2.4 |
| Map-pass model | Groq free tier (text-only, fast) | Fact extraction per chunk |
| Reduce-pass model | Gemini API free tier | Final judgment, needs vision-capable provider anyway |
| Backend API | FastAPI (Python) *or* Fastify (Node) | Pick based on team's stronger language — this spec assumes Python in code examples below |
| Job orchestration | Celery + Redis (or a simple queue) | Async retries per chunk, not one long synchronous request |
| Database | PostgreSQL 15+ (+ `pgvector` extension, for future use) | See Section 3 |
| Object storage | MinIO (local/dev) → AWS S3 or Cloudflare R2 (prod) | S3-compatible API — no code change on migration |
| Frontend | Next.js + Tailwind CSS | Dashboard, upload flow, module views |
| Auth | Clerk or NextAuth.js | Not built in MVP scope, but pick early to avoid rework |

### 2.3 Repository structure (suggested)

```
tender-ai-platform/
├── backend/
│   ├── app/
│   │   ├── api/                # FastAPI routes (upload, status, results)
│   │   ├── pipeline/
│   │   │   ├── classify.py     # page classifier (rule-based, no AI)
│   │   │   ├── extract_native.py
│   │   │   ├── extract_vision.py   # scanned + table pages
│   │   │   ├── dedupe.py        # hash lookup against boilerplate_cache
│   │   │   ├── chunk.py         # chunk assembly with overlap
│   │   │   ├── map_pass.py      # cheap model, per-chunk fact extraction
│   │   │   └── reduce_pass.py   # strong model, final judgment per module
│   │   ├── models/              # ORM models (SQLAlchemy) matching Section 3 schema
│   │   ├── storage/
│   │   │   ├── db.py            # Postgres connection
│   │   │   └── objects.py       # S3/MinIO client wrapper
│   │   └── workers/             # Celery task definitions
│   ├── migrations/              # Alembic migrations from schema in Section 3
│   └── requirements.txt
├── frontend/
│   └── (Next.js app)
├── docker-compose.yml           # postgres + minio + redis for local dev
└── .env.example
```

### 2.4 AI provider setup

- **Gemini API** — create a free API key at Google AI Studio, no credit card required for the free tier. Used for both vision extraction (scanned/table pages) and the reduce pass. Set `GEMINI_API_KEY` in environment.
- **Groq** — create a free API key at console.groq.com, no credit card required. Used for map-pass fact extraction on chunked text. Set `GROQ_API_KEY`.
- **Ollama (optional, local)** — install from ollama.com, then `ollama pull qwen2.5vl:7b` for a fully offline vision-extraction fallback (needs ~8GB+ VRAM). No API key needed; point the vision-extraction client at `http://localhost:11434` when `USE_LOCAL_VISION=true`.
- Free-tier request/rate limits vary by provider and change over time — check current quotas on each provider's site before assuming a fixed number in code; build with basic retry/backoff regardless.

### 2.5 Environment variables (`.env.example`)

```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/tender_platform

# Object storage (MinIO locally, S3-compatible in prod)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=tenders

# AI providers
GEMINI_API_KEY=
GROQ_API_KEY=
USE_LOCAL_VISION=false          # true to route vision calls to Ollama instead
OLLAMA_BASE_URL=http://localhost:11434

# Queue
REDIS_URL=redis://localhost:6379/0
```

### 2.6 Local dev setup (docker-compose services)

Run Postgres, MinIO, and Redis locally via `docker-compose.yml`:

- `postgres:15` — exposes 5432, seeded via `migrations/`
- `minio/minio` — exposes 9000 (API) / 9001 (console), create the `tenders` bucket on first run
- `redis:7` — exposes 6379, backs the Celery queue

### 2.7 Future addition (not MVP): vector index

If a "chat with this tender" feature is added later, a `chunk_embeddings` table using `pgvector` gets added — deliberately kept out of the MVP schema below since the three core modules need exhaustive page coverage, not top-k semantic retrieval.

---

## 3. Database structure (for setup)

**Engine:** PostgreSQL 15+, with the `pgvector` extension enabled (for future use — no vector columns in the MVP schema, but enabling the extension now avoids a later migration).

**Design principle:** three layers, each independently regenerable from the one below it.
- **Raw layer** (`documents`, `pages`, `extracted_tables`) — immutable once written, the source of truth for every citation.
- **Structured layer** (`chunks`, `chunk_extractions`) — derived, cheap to regenerate if extraction prompts improve.
- **Analysis layer** (`document_analysis`) — derived, what the product actually reads.
- Plus **`company_profiles`** (input data, not derived from documents) and **`boilerplate_cache`** (a cross-document lookup table, not tied to one document).

### 3.1 Full DDL

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- for future use, not used by MVP tables

-- ============================================================
-- COMPANY PROFILES — input data used by the reduce pass
-- ============================================================
CREATE TABLE company_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name        TEXT NOT NULL,
    annual_turnover      JSONB,             -- e.g. {"2023": 5.2e7, "2024": 7.1e7} (in INR)
    certifications       JSONB,             -- e.g. ["ISO 9001", "CPWD registration class A"]
    past_projects        JSONB,             -- array of {name, client, value, year, sector}
    geographic_presence  JSONB,             -- e.g. ["Maharashtra", "Gujarat"]
    sectors               JSONB,             -- e.g. ["power transmission", "civil works"]
    max_capacity_pct     NUMERIC,           -- available current bidding capacity, 0-100
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- RAW LAYER — immutable once written
-- ============================================================
CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename            TEXT NOT NULL,
    issuing_authority    TEXT,
    total_pages          INTEGER,
    status               TEXT NOT NULL DEFAULT 'uploaded'
                          CHECK (status IN ('uploaded','classifying','extracting','extracted','analyzing','ready','failed')),
    original_pdf_s3_key  TEXT,               -- pointer to object storage, not the file itself
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
    raw_text            TEXT,                -- the extracted text, whatever the source
    content_hash        CHAR(64),            -- SHA-256 of normalized raw_text, for dedupe lookups
    image_s3_key         TEXT,                -- pointer to page image in object storage
    confidence_score     NUMERIC,             -- 0.0–1.0
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_number)
);

CREATE TABLE extracted_tables (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id             UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    table_type           TEXT,                -- e.g. 'BOQ', 'schedule', 'eligibility_matrix'
    table_data           JSONB NOT NULL,       -- rows/columns as structured JSON
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- CROSS-DOCUMENT DEDUPE CACHE
-- ============================================================
CREATE TABLE boilerplate_cache (
    content_hash          CHAR(64) PRIMARY KEY,
    issuing_authority      TEXT,
    cached_extraction      JSONB,             -- reusable structured result for this exact page text
    first_seen_document_id UUID REFERENCES documents(id),
    hit_count              INTEGER NOT NULL DEFAULT 0,
    last_used_at           TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- STRUCTURED LAYER — derived, cheap to regenerate
-- ============================================================
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
    structured_json      JSONB NOT NULL,       -- {dates:[], amounts:[], criteria:[], risk_candidates:[...]}, each item cites a page
    model_used           TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- ANALYSIS LAYER — derived, what the product reads
-- ============================================================
CREATE TABLE document_analysis (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    module               TEXT NOT NULL
                          CHECK (module IN ('go_no_go','synopsis','risk_finder')),
    result                JSONB NOT NULL,       -- module-specific shape, see 3.3
    model_used            TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, module)
);

-- ============================================================
-- INDEXES — the two most frequent lookup patterns
-- ============================================================
CREATE INDEX idx_pages_document_page   ON pages (document_id, page_number);
CREATE INDEX idx_pages_content_hash    ON pages (content_hash);
CREATE INDEX idx_chunks_document       ON chunks (document_id);
CREATE INDEX idx_chunk_extractions_chunk ON chunk_extractions (chunk_id);
CREATE INDEX idx_document_analysis_doc ON document_analysis (document_id);
```

### 3.2 Table-by-table reference

| Table | Purpose | Key fields to know |
|---|---|---|
| `company_profiles` | Input data compared against tenders by the reduce pass | `annual_turnover`, `certifications`, `past_projects` — all JSONB, since fields vary by company |
| `documents` | One row per uploaded tender | `status` tracks pipeline progress end to end; `company_profile_id` links which profile to score against |
| `pages` | One row per page — the heart of the raw layer | `content_hash` drives dedupe; `image_s3_key` is a pointer only, never the binary |
| `extracted_tables` | Structured table data, linked to its page | Separate from `pages.raw_text` so BOQ/schedule rows aren't flattened into prose |
| `boilerplate_cache` | Cross-document — not scoped to one tender | Checked *before* trusting a page's extraction as "new"; `hit_count` shows dedupe is working |
| `chunks` | Defines the page ranges the map pass reads | `start_page`/`end_page` should overlap by a couple pages between consecutive chunks (handled in application logic, not the schema) |
| `chunk_extractions` | Cheap model's per-chunk output | One row per chunk; `structured_json` holds facts each tagged with a page number |
| `document_analysis` | Final output per module | One row per (document, module) pair — enforced by the `UNIQUE` constraint, so re-running analysis is an upsert, not a new row |

### 3.3 Example `document_analysis.result` shapes

```jsonc
// module = 'go_no_go'
{
  "score": 78,
  "decision": "Go",
  "criteria_matches": [
    { "criterion": "Minimum turnover", "required": "50 Cr", "company_value": "72 Cr", "status": "pass" }
  ],
  "gaps": [],
  "next_steps": ["Prepare EMD of INR 91.2 lakh", "Submit ISO 9001 certificate"]
}

// module = 'risk_finder'
{
  "risk_score": 62,
  "risks": [
    {
      "category": "Liquidated Damages",
      "clause_summary": "LD rate 1%/week, no cap stated",
      "severity": "HIGH",
      "page_ref": 214,
      "verified": true
    }
  ]
}
```

### 3.4 Notes for whoever sets this up

- Enable `pgcrypto` and `vector` extensions before running the DDL (the `vector` extension is unused by MVP tables but avoids a later migration).
- All `JSONB` columns are intentional — their shape will evolve as extraction prompts improve; don't normalize them into rigid columns.
- `pages.image_s3_key` and `documents.original_pdf_s3_key` are strings only — the actual binaries live in object storage (MinIO locally), never in Postgres.
- `document_analysis` uses `UNIQUE (document_id, module)` deliberately — re-running an analysis should upsert this row, not create a new one; keep old versions in an audit/history table only if that's explicitly needed later, not by default.
- Use a migration tool (Alembic if the backend is Python) from day one — don't hand-run this DDL against a long-lived database once real data exists.
