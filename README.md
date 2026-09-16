# Tender AI Platform

Reads Indian government tender PDFs (50–1000+ pages, mixed native text / scanned images
/ tables) and produces three outputs per tender: a Go/No-Go recommendation scored
against a company profile, a structured synopsis, and a page-cited risk list.

Full spec: [`docs/SPEC.md`](docs/SPEC.md). Architecture decisions and rationale:
[`docs/DECISIONS.md`](docs/DECISIONS.md). Rules for anyone (human or agent) working in
this repo: [`CLAUDE.md`](CLAUDE.md).

**Status:** Phases 0-3 complete. Verified against both the synthetic golden set and all
8 real tender PDFs in `documents/` (1197 real pages) against a real, live Postgres
(reached over Tailscale). Two DB schemas exist: our page-level schema is canonical, a
colleague's bronze/silver/gold schema is a derived export/reporting layer — see
`docs/ARCHITECTURE.md`. LLM access is Ollama Cloud (free tier, no API key) — see
`docs/DECISIONS.md` #28. See the implementation plan for the full phase-gated build order.

## Architecture, in one line

A Celery-orchestrated **map-reduce pipeline** over full documents (classify → extract →
dedupe → chunk → map-pass → reduce-pass → serve) — not a RAG chatbot, not an agent. Every
page of every tender is read in full; there is no retrieval step.

## Local development

Prerequisites: Docker, Docker Compose.

```bash
cp .env.example .env          # LLM access is Ollama Cloud — install ollama, `ollama` login, no API key needed
docker compose up --build
```

This brings up Postgres, MinIO, Redis, the FastAPI app, a Celery worker, Prometheus, and
Grafana. Apply the database schema:

```bash
docker compose exec api alembic upgrade head
```

This applies both migrations: `0001` (our own page-level schema — the system of record)
and `0002` (a colleague's bronze/silver/gold export/reporting schema — derived, not
authoritative; see `docs/ARCHITECTURE.md`).

**Using the shared dev Postgres instead of a local one:** the team's current dev database
runs on a colleague's machine, reachable over Tailscale (not the public internet) —
connect to that tailnet, then point `DATABASE_URL` in `backend/.env` at that host instead
of `localhost`. `pgvector` is not installed there; migration 0001 tolerates that (see
`docs/DECISIONS.md` #22) since no MVP table needs it yet.

Verify:
- `http://localhost:8000/health` — liveness
- `http://localhost:8000/ready` — readiness (checks Postgres + Redis)
- `http://localhost:8000/metrics` — Prometheus metrics
- `http://localhost:9000` (API) / `http://localhost:9001` (console) — MinIO, `minioadmin`/`minioadmin`
- `http://localhost:9090` — Prometheus
- `http://localhost:3000` — Grafana, `admin`/`admin`

## Tests

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
pytest tests/unit -v
```

Tests mock the LLM, S3, and Celery — a test run costs $0 and is deterministic (see
`CLAUDE.md` hard rule 8).

## Golden eval set (Phase 1)

`backend/evals/` holds the golden datasets pipeline phases are gated against, plus small
synthetic PDF fixtures they reference. Regenerate/extend them with:

```bash
cd backend
.venv/Scripts/python.exe scripts/build_eval_set.py
```

This is a v1, synthetic set (23 generated fixtures, 144 examples across page
classification, extraction, go/no-go, risk-finder, and adversarial cases — see
`docs/DECISIONS.md` row 14). Real anonymized tender excerpts and the actual company
profile, once available, get added as further fixtures via the same generator, not a
replacement of it. `evals/test_classification.py` passes as of Phase 2 (100% on the
synthetic set — see `docs/DECISIONS.md` row 18 for the caveat that means less than it
sounds like); the rest of `pytest evals/` is expected to keep failing with import errors
until the later pipeline phases that produce what they test are built.

## Project layout

```
backend/    FastAPI app, pipeline, Celery workers, Alembic migrations, evals, tests
frontend/   Next.js dashboard (added in Phase 8)
docs/       SPEC.md, DECISIONS.md, ARCHITECTURE.md, RUNBOOK.md
```

See `docs/SPEC.md` §Repo scaffold and the implementation plan for the full file tree and
the phase-by-phase build order.
