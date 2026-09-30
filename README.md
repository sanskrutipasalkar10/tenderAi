# Tender AI Platform

Reads Indian government tender PDFs (50–1000+ pages, mixed native text / scanned images
/ tables, including GeM tenders whose real terms live behind hyperlinked annexures, not
in the uploaded file itself) and produces four outputs per tender: a Go/No-Go
recommendation scored against a company profile (with a PQ eligibility checklist and a
TQ competitiveness score alongside it), a structured synopsis, and a page-cited risk
list.

Full spec: [`docs/SPEC.md`](docs/SPEC.md). Architecture rationale, decision-by-decision:
[`docs/DECISIONS.md`](docs/DECISIONS.md). The full build story (what broke against real
data, how it was fixed, phase by phase): [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md).
Rules for anyone (human or AI agent) working in this repo:
[`CLAUDE.md`](CLAUDE.md). Production runbook: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

**Status:** Phase 8 (observability, frontend, ship) — in progress, most of it built and
verified against real data. Backend pipeline (ingestion → GeM hyperlink fetching →
chunking → map-pass → reduce-pass → Go/No-Go/synopsis/risk-finder) and the Next.js
frontend are both built and have been driven against a real, live Postgres and real LLM
calls. `docker compose`'s Langfuse/Prometheus/Grafana services are scaffolded but have
not been verified end-to-end (see **Known gaps** below). **The spec's "<15 min p95 for a
500-page document" latency target is not yet met** at current throughput — flagged
honestly, not hidden; see `docs/DECISIONS.md` #50.

## Architecture, in one line

A Celery-orchestrated **map-reduce pipeline** over full documents (classify → extract →
fetch linked annexures → dedupe → chunk → map-pass → reduce-pass → serve) — not a RAG
chatbot, not an agent. Every page of every tender (including every page of every
hyperlinked annexure a GeM cover sheet links out to) is read in full; there is no
retrieval step.

---

## 1. Prerequisites

Install these before doing anything else:

| Tool | Version | Why |
|---|---|---|
| Python | 3.11+ | Backend (FastAPI, Celery workers, pipeline) |
| Node.js | 20+ | Frontend (Next.js 16) |
| PostgreSQL | 15+ | System of record — either your own local instance, or the team's shared instance (see §2) |
| Redis | any recent 7.x | Celery broker/backend. On Windows: install [Redis for Windows](https://github.com/tporadowski/redis/releases) (or Memurai), or run it via WSL/Docker — anything that listens on `localhost:6379` works |
| Ollama | latest | The automatic local fallback when every Gemini call fails (`ollama serve` must be running; `ollama pull qwen2.5-coder:7b` and `ollama pull qwen2.5vl:7b` for map/reduce and vision fallback respectively). Not required for a first smoke test, but every real document run has no safety net until it's set up |
| A Gemini API key | — | The **primary** LLM provider for every pipeline stage (map, reduce, vision) — see §3. Get one from [aistudio.google.com](https://aistudio.google.com/) |
| Docker + Docker Compose | optional | An alternative all-in-one way to bring up Postgres/MinIO/Redis/Langfuse/Grafana — see §6. Not required if you already have Postgres/Redis running natively, which is the path this project has actually been verified against |

## 2. Get a Postgres instance

You need a reachable Postgres 15+ with two migrations applied (`0001`: this project's own
page-level schema — the system of record; `0002`–`0004`: a colleague's bronze/silver/
gold export schema plus this project's own incremental additions — see
`docs/ARCHITECTURE.md`'s export-layer section for why there are two schemas and which
one is authoritative — **never treat the bronze/silver/gold tables as a citation
source**).

You have two options:

**Option A — your own local Postgres.** Create a database and a user matching whatever
you'll put in `DATABASE_URL` (see §3). `pgvector` does *not* need to be installed — the
`vector` extension is enabled by the spec for future use, but no table actually has a
vector column yet, and migration `0001` tolerates its absence gracefully
(`docs/DECISIONS.md` #22).

**Option B — the team's shared dev instance.** It currently runs on a teammate's own
machine, reached over [Tailscale](https://tailscale.com/) (not the public internet) at
`100.65.111.7:5432` — connect to that tailnet first, then use that host in
`DATABASE_URL`. **If you are the person whose machine hosts it, use `localhost`
instead of the Tailscale IP** — you're already local to it. Ask a teammate for the real
username/password if you're connecting remotely; nothing here assumes you already have
them.

Either way, once you can reach it, apply migrations — see §4 step 5.

## 3. Configure environment variables

```bash
cp .env.example backend/.env
```

Open `backend/.env` and fill in, at minimum:

- `DATABASE_URL` — from §2 above.
- `GEMINI_API_KEY` — from [aistudio.google.com](https://aistudio.google.com/). **This is
  required for real analysis to run** — without it, every map/reduce/vision call falls
  straight through to the local Ollama fallback (or fails outright if Ollama isn't
  running either). If your key has an `AQ.` prefix, it's a **Vertex AI Express Mode**
  key specifically — this project's Gemini client (`app/llm/client.py`) is already
  written for that endpoint/payload shape, so it should just work; see
  `docs/DECISIONS.md` #76 if you hit a `403 API_KEY_SERVICE_BLOCKED` (it means the
  opposite mismatch — a standard AI-Studio key being used where an Express key was
  expected, or vice versa).
- `AUTH_PASSWORD_HASH` — a bcrypt hash of whatever password you want to log into the
  frontend with. Generate it with the venv active (see §4 step 2):
  ```bash
  python -c "from app.core.security import hash_password as h; print(h('your-password'))"
  ```
  Paste the output in. `AUTH_USERNAME` defaults to `admin` — change it if you like.
- `JWT_SECRET_KEY` — any random string for local dev (`change-me-in-every-environment`
  is the placeholder; don't ship that value to anything real).

Everything else in `.env.example` has a working default for local development
(MinIO/S3, Redis, CORS, upload limits, the GeM link-fetching allowlist). Leave
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` blank unless you've also brought up the
Langfuse service (§6) — tracing no-ops cleanly without them.

Also copy the frontend's env file — its one variable already defaults correctly for
local dev:

```bash
cp frontend/.env.example frontend/.env.local
```

## 4. Run the backend natively (the verified path)

This is the exact sequence that has actually been run and confirmed working end-to-end
against real tender PDFs and a real Postgres — prefer it over Docker Compose (§6) unless
you specifically need the containerized services.

**Step 1 — object storage.** You need something S3-compatible reachable at
`S3_ENDPOINT_URL` (`http://localhost:9000` by default). The simplest way, even if
you're not using Docker Compose for anything else, is to run just MinIO in its own
container:
```bash
docker run -d -p 9000:9000 -p 9001:9001 --name tender-minio \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```
(No Docker available? Install MinIO's [standalone binary](https://min.io/download) and
run `minio server /data` directly.) Then create the bucket named in `.env`
(`tenders` by default) — easiest via the console at `http://localhost:9001`
(`minioadmin`/`minioadmin`), or `mc mb local/tenders` if you have the `mc` CLI.

**Step 2 — Python environment:**
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

**Step 3 — start Redis** (if it isn't already running as a service — see §1's table).
Confirm with `redis-cli ping` → `PONG`.

**Step 4 — start Ollama** (optional but recommended, for the fallback path):
```bash
ollama serve
```
Leave this running in its own terminal.

**Step 5 — apply database migrations:**
```bash
# still in backend/, venv active
alembic upgrade head
```
This applies `0001` (this project's own page-level schema — `documents`, `pages`,
`chunks`, `chunk_extractions`, `document_analysis`, `boilerplate_cache`,
`company_profiles`), `0002` (the colleague's derived bronze/silver/gold export schema —
untouched, reporting-only), `0003` (statutory/financial company-profile fields), and
`0004` (the `pages.source_url` column plus `linked_document_cache`, for GeM hyperlinked
annexures). Safe to re-run — every migration here is idempotent (`IF NOT EXISTS`
throughout).

**Step 6 — start the API server** (new terminal, venv active, still in `backend/`):
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Step 7 — start the Celery worker** (another new terminal, venv active, still in
`backend/`):
```bash
python -m celery -A app.workers.celery_app worker --pool=solo --loglevel=info -Q default,llm
```
`--pool=solo` is required on Windows (Celery's default prefork pool doesn't work there).
On macOS/Linux you can drop it and get real concurrency instead. **The `-Q default,llm`
is required** — `ingest_document_task` (`tasks_ingest.py`) and `map_pass_chunk_task`
(`tasks_map.py`) both declare `queue="llm"` (per `celery_app.py`'s docstring: isolate
slow LLM-calling tasks from cheap ones), and a worker started with no `-Q` flag only
consumes `task_default_queue` (`"default"`) — it silently never sees anything published
to `"llm"`, including `ingest_document_task`, the very first task in the pipeline. A
document uploaded against a worker missing this flag sits at `status="uploaded"`
forever with no error anywhere: the upload itself succeeds (the task publishes to Redis
fine), the task just has no consumer. Caught for real running natively on Windows —
uploads silently never left "uploaded," and the Celery message ended up sitting in
Redis's `llm` list uninspected because a leftover second `redis-server.exe` process
happened to be squatting on the same port on the IPv4 stack while the real (Windows
service) Redis instance — where the actual traffic was going — was IPv6-only, so a bare
`redis-cli` (which defaults to `127.0.0.1`) silently inspected the wrong, always-empty
instance. If you ever see this class of symptom again, check for more than one
process listening on `6379` before assuming the task dispatch itself is broken. This
native single-worker path is otherwise equivalent to the `docker-compose.yml` two-worker
split (`celery-worker-llm` with `-Q llm`, `celery-worker-default` with `-Q default`),
which was already correctly configured and not affected by this gap.

**Verify the backend is up:**
- `http://localhost:8000/health` — liveness
- `http://localhost:8000/ready` — readiness (checks Postgres + Redis)
- `http://localhost:8000/docs` — interactive API docs (FastAPI's auto-generated Swagger UI)

## 5. Run the frontend

New terminal:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000`. Log in with the `AUTH_USERNAME`/password you set in §3
(the plaintext password you hashed, not the hash itself). The frontend keeps that one
shared credential in `localStorage` — there's no per-user session or signup flow by
design (`docs/DECISIONS.md` #44); it's a single internal bid-team login.

**Create a company profile** before uploading a tender — the Go/No-Go module needs one
to compare against. Either use the **Company profiles** page in the frontend nav
directly, or, for a batch/scripted seed:
```bash
# in backend/, venv active
python scripts/seed_company_profile.py scripts/seed_data/<your-file>.json
```

**Upload a tender:** the "Upload tender" button in the nav accepts a PDF and kicks off
the full pipeline asynchronously — you'll see live progress (classifying → extracting →
analyzing → ready) on the document's page, including a breakdown of how many pages came
from the uploaded file itself versus how many were found and fetched from GeM hyperlinked
annexures, so the page count never looks confusingly mismatched.

## 6. Alternative: Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

This brings up Postgres (with `pgvector` preinstalled — not currently required, but
saves a future migration), MinIO, Redis, the FastAPI app, two Celery worker containers,
Langfuse (self-hosted — never Langfuse Cloud, since traces carry real tender text),
Prometheus, and Grafana, all wired together. Apply migrations the same way, just inside
the container:
```bash
docker compose exec api alembic upgrade head
```

**Important caveats, stated plainly rather than discovered the hard way:**
- This spins up its **own, empty** Postgres/MinIO — not the shared team instance from
  §2 Option B. If you want the real, already-processed project data, point `DATABASE_URL`
  at the shared instance instead of using this compose file's `postgres` service, or
  accept that you're starting from zero.
- The `celery-worker-llm` / `celery-worker-default` two-container split does not
  currently do anything different from a single worker — see §4 step 7's note. Both
  containers will start fine; only `celery-worker-default` will ever pick up work.
- The Langfuse/Prometheus/Grafana services are scaffolded correctly but have **not**
  been verified end-to-end in this project's own dev environment (Docker wasn't
  available there) — no real trace or dashboard has actually been confirmed rendering.
  They may just work; they simply haven't been checked the way everything else in this
  README has been.

Service URLs once up:
- `http://localhost:8000` — API (same endpoints as §4)
- `http://localhost:3002` — dockerized frontend (`npm run dev` on your host, §5, still
  uses port 3000 — both are allowed through CORS simultaneously)
- `http://localhost:9000` / `:9001` — MinIO API / console (`minioadmin`/`minioadmin`)
- `http://localhost:3001` — Langfuse (sign up on first visit, create a project, paste
  its keys into `.env`'s `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`)
- `http://localhost:9090` — Prometheus
- `http://localhost:3000` — Grafana (`admin`/`admin`) — **note this collides with a
  natively-run frontend's port 3000** if you mix approaches; only run one or the other
  on that port.

## 7. Tests

```bash
cd backend
.venv/Scripts/activate
pytest tests/ evals/ -q
```
Everything here mocks the LLM, S3/MinIO, and runs Celery in eager/synchronous mode — a
full test run costs $0, needs no real Postgres/Redis/Gemini key, and is fully
deterministic (`CLAUDE.md` hard rule 8). At last count: 336 passed, 1 skipped.

Lint/type-check:
```bash
ruff check .
mypy app/
```

Frontend:
```bash
cd frontend
npm run lint
npm run build   # also catches type errors — `tsc` runs as part of the Next.js build
```

## 8. Project layout

```
backend/    FastAPI app, pipeline, Celery workers, Alembic migrations, evals, tests
  app/
    api/            HTTP routes
    core/           config, exceptions, logging, tracing
    guardrails/      prompt-injection + SSRF-style URL-fetch checks (input_checks.py, output_checks.py, link_checks.py)
    llm/             client.py — the ONLY file allowed to talk to Gemini/Ollama; router.py picks the model per task
    models/          SQLAlchemy ORM models
    pipeline/        classify → extract → fetch_links (GeM annexures) → dedupe → chunk → map_pass → reduce_pass
    prompts/         every prompt as a versioned .md file, loaded via registry.py — never inline in Python
    services/        ingestion.py — orchestrates one document's classify/extract/persist loop
    storage/         Postgres (db.py) + S3/MinIO (objects.py) clients
    workers/         Celery task definitions + celery_app.py config
  migrations/        Alembic — 0001 (our schema) . 0002 (colleague's export schema) . 0003 (statutory fields) . 0004 (GeM hyperlinks)
  evals/             golden-dataset pytest harness (backend/evals/datasets/*.jsonl)
  scripts/           one-off/batch scripts — seed_company_profile.py, build_eval_set.py, local_pipeline_test.py
frontend/   Next.js 16 (App Router) dashboard — lib/api.ts is the ONLY file that calls the backend
docs/       SPEC.md, DECISIONS.md, ARCHITECTURE.md, RUNBOOK.md, BACKEND_GUIDE.md, DEVELOPMENT_HISTORY.md
```

## 9. Known gaps (flagged, not hidden)

- **Latency target not met**: the spec's "<15 min p95 for a 500-page document" is not
  achievable yet at Ollama Cloud's free-tier fallback throughput; Gemini as primary
  measured dramatically faster in real runs (`docs/DECISIONS.md` #76-77), but this
  hasn't been re-verified against a full 500-page document specifically.
- **Docker Compose's Langfuse/Prometheus/Grafana stack** is unverified end-to-end (§6).
- **Celery's `llm`/`default` queue split** is scaffolded in `celery_app.py` and
  `docker-compose.yml` but not actually wired up via per-task `queue=` routing (§4
  step 7) — currently harmless (everything runs on one queue either way) but worth
  fixing before relying on the two-container split for real isolation.
- **No document-level upload dedup**: uploading the same PDF twice creates two entirely
  separate `Document` rows and reprocesses everything from scratch (re-chunking,
  re-fetching GeM annexures, re-running every LLM call) — there's no "have I already
  processed this exact file" check.
- **`ClassificationError`/`CitationVerificationError`** exist in the failure taxonomy
  but are deliberately unused — see their docstrings in `app/core/exceptions.py`.
