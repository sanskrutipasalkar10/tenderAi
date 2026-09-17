# Runbook — Tender AI Platform

Operational reference for running, debugging, and recovering this system. Written
against what's actually built through Phase 8 (see `docs/DEVELOPMENT_HISTORY.md` for
how it got here, `docs/DECISIONS.md` for why each piece works the way it does).

## Bringing up the stack

```bash
cp .env.example .env   # fill in real values — never commit .env
docker-compose up --build
```

Services and ports: API `:8000` (`/health`, `/ready`, `/metrics`, `/docs`), MinIO
`:9000`/console `:9001`, Redis `:6379`, Postgres `:5432`, Langfuse `:3001` (self-hosted,
docs/DECISIONS.md #52), Prometheus `:9090`, Grafana `:3000` (admin/admin by default —
change `GF_SECURITY_ADMIN_PASSWORD` before anything but local dev), celery-exporter
`:9808`. Two Celery worker pools run (`celery-worker-llm` at `--concurrency=4`,
`celery-worker-default` at `--concurrency=8` — docs/DECISIONS.md #47), not one.

**Known gap:** the exact service definitions above (Langfuse, celery-exporter, Grafana
provisioning) were written and unit-tested but never run through a real
`docker-compose up` — this dev environment has no Docker. First real deployment should
treat this as day-one verification, not an assumption.

## Known failure cases per pipeline stage

Failures are typed (`app/core/exceptions.py`) into a fixed taxonomy, each with its own
`status_code` and logged automatically by the shared exception handler
(`request.failed` — path, error_type, status_code, detail) before the user-facing
message goes out. `ClassificationError` and `CitationVerificationError` are defined but
never actually raised, by design (see their docstrings) — classification is a total
function with no failure branch, and an unresolvable citation is modeled as
`verified: false` data, not an exception.

| Stage | What actually fails, in practice | Symptom | What to do |
|---|---|---|---|
| Upload / guardrails | Corrupt/0-page PDF, over `MAX_UPLOAD_PAGES`, doesn't look like a tender | `DataQualityError`, 422, before any Document row exists | Check the response `message` — it names the specific reason. If a real tender is wrongly rejected as "not a tender," see `app/guardrails/input_checks.py`'s `TENDER_SIGNAL_TERMS`/`NEGATION_PHRASES` — tune with real evidence (docs/DECISIONS.md #46), not a guess |
| Ingestion (classify/extract/vision) | A single page's vision call fails after cloud+local fallback both exhausted | `ProviderError` (502) surfaces from `tasks_ingest.py`'s Celery retry (3 attempts, 30s delay); the whole document's ingestion task retries, not just one page — see "known architectural gap" below | Check Celery worker logs for `llm.call_failed_after_retries`. If it's a real Ollama Cloud outage, wait and let the Celery retry handle it; if persistent, check `ollama list` on the host and `OLLAMA_BASE_URL` connectivity |
| Map pass | One chunk's LLM call fails after fallback, or never returns valid JSON after 2 parse retries | `ProviderError`; `tasks_map.py` retries only that one chunk (docs/SPEC.md's Phase 4 gate) | Check `chunk_extractions` for that `chunk_id` — if missing, the chunk never completed. Re-enqueue: `map_pass_chunk_task.delay(str(chunk_id))` from a Python shell, or re-run `run_map_pass_for_document` for the whole document (safe — upsert-free per-chunk inserts, no dedup needed since each chunk_id only ever gets one extraction row) |
| Reduce pass | A module's LLM call fails, or company_profile is incomplete | `ProviderError`, or a clean `Conditional-Go` with `gaps[]` (not a failure — working as designed, docs/DECISIONS.md #38) | For a real failure: re-run that one module — `run_go_no_go`/`run_synopsis`/`run_risk_finder` all upsert (`document_analysis`'s `UNIQUE(document_id, module)`), so re-running is always safe, never creates a duplicate |
| Citation verification | A `page_ref` doesn't resolve to a real `pages` row | Not an exception — `risk_finder.risks[].verified: false`, kept and shown, never dropped (docs/SPEC.md §7) | If verified:false shows up on a citation that should be real, check whether `pages` actually has a row for that `(document_id, page_number)` — a real gap here means a map-pass page_ref hallucination slipped past the schema check, worth a golden-eval regression test |
| Auth | Wrong credential, or 5 failed attempts in 300s for one username | `AuthenticationError` (401) or `RateLimitError` (429) | Rate limit is a fixed-window Redis counter keyed `login_attempts:<username>` — clear it manually (`redis-cli DEL login_attempts:admin`) only if you're certain the lockout isn't currently protecting against a real attack |

**Known architectural gap, not yet fixed:** `tasks_ingest.py` processes an entire
document (every page, including every vision call) in one Celery task, unlike
`tasks_map.py`'s one-task-per-chunk design. A single page's persistent failure retries
the *whole document's* ingestion, not just that page. Fixing this means fanning
ingestion out per-page the way map_pass is fanned out per-chunk — a real architectural
change (see `celery_app.py`'s own docstring), not done here to stay in this phase's
scope.

## A Celery task is stuck or a chunk keeps failing

1. Check which queue it's on: `celery -A app.workers.celery_app inspect active` —
   compare against `docs/DECISIONS.md #47`'s expected queue (`llm` for map/reduce/
   ingestion, `default` for chunk-building).
2. Check the Grafana dashboard (`Tender AI Platform`, auto-provisioned) for that task
   name's p95 duration — if it's within the normal real-measured range (~6-135s per
   chunk, docs/DECISIONS.md #50), it may just be legitimately slow, not stuck.
3. A task past `LLM_TASK_SOFT_TIME_LIMIT`/`LLM_TASK_TIME_LIMIT` (600s/660s,
   `celery_app.py`) gets killed by Celery itself and retried — this is expected
   behavior, not a bug, for the rare pathological case app.llm.client's own internal
   timeout doesn't catch.
4. If a specific chunk repeatedly fails after all retries are exhausted (3 attempts,
   `tasks_map.py`), check Langfuse (docs/DECISIONS.md #52) for that call's actual
   input/output — real prompt content is there, which is usually the fastest way to
   see *why* (e.g. a genuinely malformed/empty page, not a transient outage).
5. Last resort: manually re-enqueue via a Python shell (`from app.workers.tasks_map
   import map_pass_chunk_task; map_pass_chunk_task.delay(str(chunk_id))`) — safe, since
   `run_map_pass` doesn't upsert per-chunk (each chunk_id only ever produces one
   `chunk_extractions` row in normal operation, so a genuine re-run after a real
   failure is the only way a second row would appear — check for duplicates first if
   this has happened before).

## A free-tier provider quota is exhausted mid-pipeline

Ollama Cloud is currently the only configured provider (docs/DECISIONS.md #28), on a
free-tier account with no payment method attached — a quota/rate-limit hit surfaces as
a 429 or 5xx, which `app/llm/client.py`'s retry-with-backoff already handles up to
`DEFAULT_NUM_RETRIES` (1) before raising `ProviderError`, and `complete_for_task`
automatically falls back to a genuinely local Ollama model (`qwen2.5-coder:7b` for
map/reduce, `qwen2.5vl:7b` for vision — docs/DECISIONS.md #32) rather than stopping the
pipeline outright. If BOTH cloud and local are exhausted/unavailable:
1. Check `ollama list` on the host actually has the local fallback models pulled.
2. Check Langfuse/logs for `llm.falling_back_to_local` — confirms the fallback was
   even attempted, and with what error.
3. There is no paid-tier fallback configured (docs/DECISIONS.md #49: $0 required
   spend is a deliberate choice, not a temporary gap) — a sustained real outage means
   waiting it out or (a deliberate scope decision, not a default) adding a paid
   provider.

## Re-running analysis for a single document without reprocessing pages

Every stage is idempotent by design, so re-running only what's actually needed is
always safe:
- **Just the reduce pass** (e.g. company_profile was updated): call
  `run_go_no_go`/`run_synopsis`/`run_risk_finder` directly — `document_analysis`'s
  `UNIQUE(document_id, module)` means each upserts in place (docs/DECISIONS.md #40),
  never duplicates. Pages/chunks/chunk_extractions are untouched.
- **Just the map pass for one chunk**: re-enqueue that chunk's task (see above) —
  doesn't touch ingestion or other chunks.
- **Re-chunking** (e.g. `CHUNK_SIZE_PAGES` changed): `build_chunks` creates new `chunks`
  rows; old chunks/chunk_extractions for that document aren't automatically cleaned up
  — delete them first (`DELETE FROM chunks WHERE document_id = ...` cascades to
  `chunk_extractions` per the DDL's `ON DELETE CASCADE`) or you'll get facts double-
  counted in `_aggregate_chunk_facts`.
- **Never re-run ingestion** just to refresh analysis — it re-classifies/re-extracts
  every page (the most expensive stage) for zero benefit if only the reduce pass
  needs updating.

## Data export / deletion

Shallow scope, per Tier 2 (`docs/SPEC.md`'s tier notes — full exit-strategy planning is
explicitly out of scope). What exists today:
- **Export**: every real fact is already in Postgres (`pages.raw_text`,
  `chunk_extractions.structured_json`, `document_analysis.result`) plus the original
  PDF in S3/MinIO (`documents.original_pdf_s3_key`) — a straight `pg_dump`/`SELECT`
  plus an S3 object copy covers a full export for one document today; no dedicated
  export endpoint exists yet.
- **Deletion**: `documents` cascades to `pages`/`chunks`/`chunk_extractions`/
  `document_analysis`/`extracted_tables` via the DDL's own `ON DELETE CASCADE` — a
  plain `DELETE FROM documents WHERE id = ...` is otherwise complete. **Exception**:
  `boilerplate_cache.first_seen_document_id` is NOT cascaded (docs/DECISIONS.md #31,
  deliberate — the cache entry may still be referenced by/relevant to *other*
  documents that share that exact content hash) — null or re-attribute that FK first,
  or the delete will fail on the constraint.
- Real tender PDFs and the company_profiles seed data are gitignored, never in git
  history to worry about (docs/DECISIONS.md #27, #51) — only the live Postgres/S3
  actually holds them, so deletion there is genuinely complete.

## On-call ownership per subsystem

No retrieval subsystem exists (not RAG — docs/DECISIONS.md #4), so this list is
shorter than a typical GenAI system's:
- **Ingestion** (classify/extract/vision, `app/pipeline/classify.py`,
  `extract_native.py`, `extract_vision.py`, `dedupe.py`): rule-based + one LLM call
  type (vision). Failure mode is almost always either a real Ollama outage or a
  genuinely unusual page (calibration issue — see docs/DECISIONS.md #25/#26 for the
  kind of real-document surprises this has already hit).
- **Pipeline** (chunk/map/reduce, `app/pipeline/chunk.py`, `map_pass.py`,
  `reduce_pass.py`, `citation_verify.py`): the highest LLM-call volume, and where
  most of this project's real bugs have been found (docs/DECISIONS.md #33-42) — check
  Langfuse first for any real incident here.
- **API/auth** (`app/api/*`, `app/core/security.py`): single shared credential
  (docs/DECISIONS.md #44) — a real incident here is almost certainly the rate limiter
  (`app/cache/redis_cache.py`) or a Redis outage, not an app bug.
- **Infra** (Postgres, MinIO, Redis, Celery, Langfuse, Prometheus/Grafana): standard
  docker-compose service health — `docker-compose ps`, each service's own healthcheck.

## Quick reference

| What | Where |
|---|---|
| Failure taxonomy | `app/core/exceptions.py` |
| Every technical decision + why | `docs/DECISIONS.md` |
| The story behind each decision | `docs/DEVELOPMENT_HISTORY.md` |
| Requirements (frozen) | `docs/SPEC.md` |
| Bronze/silver/gold export mapping | `docs/ARCHITECTURE.md` |
| Real DB credentials | `backend/.env` (gitignored — see `.env.example` for shape) |
| Cost/token volume per document | `python scripts/report_cost.py` |
| Seed a company profile | `python scripts/seed_company_profile.py <path>.json` |
