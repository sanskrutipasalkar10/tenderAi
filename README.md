# Tender AI Platform

Reads Indian government tender PDFs (50–1000+ pages, mixed native text / scanned images
/ tables) and produces three outputs per tender: a Go/No-Go recommendation scored
against a company profile, a structured synopsis, and a page-cited risk list.

Full spec: [`docs/SPEC.md`](docs/SPEC.md). Architecture decisions and rationale:
[`docs/DECISIONS.md`](docs/DECISIONS.md). Rules for anyone (human or agent) working in
this repo: [`CLAUDE.md`](CLAUDE.md).

**Status:** Phase 0 (scaffold) complete. See the implementation plan for the full
phase-gated build order.

## Architecture, in one line

A Celery-orchestrated **map-reduce pipeline** over full documents (classify → extract →
dedupe → chunk → map-pass → reduce-pass → serve) — not a RAG chatbot, not an agent. Every
page of every tender is read in full; there is no retrieval step.

## Local development

Prerequisites: Docker, Docker Compose.

```bash
cp .env.example .env          # fill in GEMINI_API_KEY / GROQ_API_KEY when you reach Phase 3
docker compose up --build
```

This brings up Postgres, MinIO, Redis, the FastAPI app, a Celery worker, Prometheus, and
Grafana. Apply the database schema:

```bash
docker compose exec api alembic upgrade head
```

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
pip install -r requirements.txt
pytest tests/unit -v
```

Tests mock the LLM, S3, and Celery — a test run costs $0 and is deterministic (see
`CLAUDE.md` hard rule 8).

## Project layout

```
backend/    FastAPI app, pipeline, Celery workers, Alembic migrations, evals, tests
frontend/   Next.js dashboard (added in Phase 8)
docs/       SPEC.md, DECISIONS.md, ARCHITECTURE.md, RUNBOOK.md
```

See `docs/SPEC.md` §Repo scaffold and the implementation plan for the full file tree and
the phase-by-phase build order.
