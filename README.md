# Tender AI Platform

Reads Indian government tender PDFs (50–1000+ pages, mixed native text / scanned images
/ tables) and produces three outputs per tender: a Go/No-Go recommendation scored
against a company profile, a structured synopsis, and a page-cited risk list.

Full spec: [`docs/SPEC.md`](docs/SPEC.md). Architecture decisions and rationale:
[`docs/DECISIONS.md`](docs/DECISIONS.md). Rules for anyone (human or agent) working in
this repo: [`CLAUDE.md`](CLAUDE.md).

**Status:** Phase 0 (scaffold) complete, Phase 1 (golden eval set) in place with a
synthetic v1 dataset — pending real tender/company-profile examples. See the
implementation plan for the full phase-gated build order.

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
replacement of it. `pytest evals/` is expected to fail with import errors until the
pipeline phases that produce what it tests (Phase 2 onward) are built — that's the
correct state until then.

## Project layout

```
backend/    FastAPI app, pipeline, Celery workers, Alembic migrations, evals, tests
frontend/   Next.js dashboard (added in Phase 8)
docs/       SPEC.md, DECISIONS.md, ARCHITECTURE.md, RUNBOOK.md
```

See `docs/SPEC.md` §Repo scaffold and the implementation plan for the full file tree and
the phase-by-phase build order.
