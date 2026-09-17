# Development History — Tender AI Platform (Phase 0 → Phase 7)

This is a narrative build log: what was built in each phase, what broke in the real
world (not in theory), and how each problem was actually fixed. `docs/DECISIONS.md` is
the terse, numbered reference table this document draws on — every `#N` citation below
points to a row there with the full technical detail. `docs/SPEC.md` is the frozen
requirements doc; `docs/ARCHITECTURE.md` covers the bronze/silver/gold export layer.

**What this system is:** a pipeline (not an agent, not RAG) that reads full Indian
government tender PDFs — 50 to 1000+ pages, mixed native text / scanned images / ruled
tables — and produces three outputs per tender: a Go/No-Go recommendation scored
against a company's profile, a structured synopsis, and a page-cited risk list. Every
claim in every output carries a `page_ref` a user can click to see the source page —
that citation is the product's actual trust mechanism (there's no separate approve/
override workflow).

---

## Phase 0 — Spec & scaffold

**Built:** `docs/SPEC.md` (the frozen requirements, written from the source
implementation-plan spec, made CI/eval-gateable), `docs/DECISIONS.md` (seeded with the
first 12 architecture decisions), the repo skeleton (`app/api`, `app/core`,
`app/pipeline`, `app/llm`, `app/prompts`, `app/guardrails`, `app/models`,
`app/storage`, `app/workers`, `app/services`), Alembic wired to migration 0001 (the
spec's own DDL, applied verbatim — `documents`, `pages`, `extracted_tables`,
`boilerplate_cache`, `chunks`, `chunk_extractions`, `document_analysis`,
`company_profiles`), `docker-compose.yml` (Postgres+pgvector, MinIO, Redis, API,
Celery worker, Prometheus, Grafana), GitHub Actions CI (ruff + mypy + pytest), and
`CLAUDE.md` (the project's own hard rules — provider isolation, prompt versioning, no
business logic in prompts, Pydantic validation on every LLM boundary, $0/deterministic
tests, timeout+retry+backoff on every external call).

**Foundational decisions made and confirmed with the user before writing code:**
Tier 2 (Internal/Pilot, not customer-facing) · Python/FastAPI · Celery+Redis
map-reduce pipeline, deliberately not an agent framework (nothing in this system
requires an LLM to choose the next step — classification is rule-based, map/reduce run
one fixed prompt each) · the citation-verification UI as the HITL mechanism, not a
separate approve/override workflow · GitHub repo hosted publicly, at the user's
explicit choice (#15).

**Problem — repo push kept failing:** fine-grained GitHub PATs repeatedly denied the
push despite having the right Contents permission. Root cause: pushing
`.github/workflows/*` needs the separate `workflow` OAuth scope, which a fine-grained
token doesn't obviously surface as missing. **Fix:** switched to `gh`'s own OAuth
device flow with explicit `repo,workflow` scopes — worked on the first attempt (#16).

---

## Phase 1 — Golden eval set (built before the pipeline that produces the data)

**Built:** `scripts/build_eval_set.py`, a synthetic-fixture generator producing 23
small, *genuinely realistic* PDFs (real inserted text for native pages, real rendered
PNGs with no text layer for scanned pages, real ruled grids for tables) and 144 golden
examples across 5 datasets (`golden_pages`, `golden_extraction`, `golden_go_no_go`,
`golden_risk_finder`, `golden_adversarial`).

**Why synthetic first:** no real tender data existed yet at this point, and the
Build Kit's own phase gate requires the eval set to exist *before* the pipeline that
will be measured against it — building fixtures that are genuine PDFs (not just JSON
labels) meant Phase 2's classifier would be tested against real extraction behavior
from day one, not just labels (#14). Real tender PDFs arrived from the user shortly
after and became the *second*, higher-value validation source used throughout every
later phase — see "The real-data validation loop" below.

---

## Phase 2 — Ingestion, classification, native extraction, storage (no LLM)

**Built:** `app/pipeline/classify.py` (rule-based, zero LLM calls — text length +
embedded-image presence + ruled-line grid detection via PyMuPDF's own vector-drawing
data), `app/pipeline/extract_native.py` (PyMuPDF text extraction + pdfplumber table
extraction), `app/models/*` (SQLAlchemy models matching the DDL), `app/storage/db.py`
and `app/storage/objects.py` (MinIO/S3 client), `app/api/routes_ingest.py`,
`app/workers/tasks_ingest.py`.

**Problem — no live Postgres yet:** the colleague's (Sapana's) database wasn't
reachable yet and Docker wasn't available in this dev environment. **Fix:** built
honest mocked-DB unit tests (`FakeSession` classes) that still ran real content
(genuine fixture PDFs) through real classify/extract code — only the persistence layer
was faked, so real extraction bugs were still caught (#19). Real integration tests
against the live DB were added once Sapana's Postgres became reachable.

**Problem — moto's S3 mock silently bypassed:** `mock_aws` only intercepts AWS's own
default endpoints; a custom `endpoint_url` (needed for real MinIO/S3-compatible
storage) made tests try a real network call instead of using the mock. **Fix:** the S3
client only sets `endpoint_url` when configured, so tests can blank it out and get
real mocking while production always sets it via `.env` (#20).

**Once Sapana's Postgres became reachable (via Tailscale — see below), two more real
bugs surfaced immediately:**
- **FK resolution failure:** `Document.company_profile_id`'s foreign key crashed with
  `NoReferencedTableError` because SQLAlchemy only knows about tables whose model class
  has actually been imported somewhere in the running process — only `Document`/`Page`
  had been imported directly. **Fix:** `app/models/__init__.py` now imports every model
  module, so importing the package always registers the full metadata graph (#24).
- **Migration collision:** the shared dev database already had a `company_master_profile`
  table (with a real row in it) created independently before migration 0002 first ran.
  **Fix:** `CREATE TABLE IF NOT EXISTS`, not a plain `CREATE TABLE` (#23).

---

## Phase 3 — Vision extraction + boilerplate dedupe

**Built:** `app/llm/client.py` and `app/llm/router.py` (the provider-isolation layer —
every LLM call in the whole codebase goes through these two files), `app/pipeline/
extract_vision.py`, `app/pipeline/dedupe.py` (SHA-256 content-hash cache), `app/
guardrails/input_checks.py` (the "is this a tender" heuristic, built here but not
wired into the actual upload route until Phase 6).

**Problem — litellm silently mangled images:** litellm 1.56.5's `ollama/` provider
stringifies a multimodal `content` list into the prompt via Python's dict repr — the
model receives the literal text `"[{'type': 'image_url', ...}]"`, not an image, and
reports seeing nothing. Its `ollama_chat/` provider sends the list as-is, which
Ollama's real API schema rejects outright (it wants `content: str` + a separate
`images: [base64...]` array). **Fix:** bypass litellm for any image-bearing Ollama
call and hit Ollama's native `/api/chat` directly with the correct payload shape — this
was the *first* of what became a pattern of routing around litellm/Ollama
incompatibilities (#29).

**Problem — a real scanned page overflowed the model's context window:** at 150 DPI, a
rendered scanned page produced a base64 image large enough to blow past the model's
262K-token context window (`"prompt is too long: 381989"`). **Fix:** dropped to 100
DPI — verified the resulting transcription was still accurate and complete against a
real vendor-approval table with 7 rows of company data (#30).

**The provider swap (user-directed mid-phase):** the original plan was Gemini (vision +
reduce) + Groq (map). The user asked to use Ollama Cloud instead. Verified free-tier
availability by hand (`ollama run <model>:cloud`) before committing — the largest
models on the account returned 402 Payment Required, but `gpt-oss:20b-cloud`,
`gpt-oss:120b-cloud`, and `gemma4:cloud` all worked free, and `gemma4:cloud`'s vision
capability was confirmed by sending it a real scanned page and getting a correct,
detailed transcription back (#28).

### The real-data validation loop starts here

This is also the point where 8 real Indian government tender PDFs (1197 pages total)
arrived from the user and became the primary validation source for everything after —
**never committed to git** (`documents/*.pdf` is gitignored; these are real,
business-sensitive procurement documents and the repo is public, #27). Running the
rule-based classifier against them immediately found two real calibration bugs no
synthetic fixture had exposed:

- **False-positive table detection:** a BHEL tender's letterhead page has a legacy
  vector-embedded Tamil-script font whose glyphs are drawn as tiny line strokes
  (10-45pt). The original 10pt line-length threshold let this through and
  false-positived the letterhead as a "table." Real table borders on the same document
  measured 495-755pt. **Fix:** raised the threshold to 60pt — re-verified both the
  golden eval (still 100%, 109/109) and the real false positive (#25).
- **Wrong header-row detection:** 130 of 135 real BOQ-style tables have 1-3
  title/metadata rows before the actual column-header row; the naive "row 0 is the
  header" assumption extracted a title fragment as the table's headers. Multi-page
  tables also repeat the same preamble on every continuation page without repeating
  the real header — an earlier fix over-corrected and mislabeled a data row as a
  header on those pages. **Fix:** skip leading single-cell "preamble" rows to find the
  real header, and detect continuation pages by checking whether the first dense row's
  first cell looks like a bare serial number. Re-verified: 69 pages got a real header,
  69 were correctly flagged as headerless continuations with all rows preserved, 2715
  total data rows captured (#26).

**Connecting to Sapana's real Postgres:** her database runs on her own machine, not a
shared server, and isn't on the same LAN — reached via Tailscale (host `100.65.111.7`,
#21). `pgvector` turned out not to actually be installed on that real instance (only
`pgcrypto` is) — since no MVP table uses `vector` anyway, migration 0001 now attempts
it inside a `SAVEPOINT` and continues with a warning on failure rather than blocking
the whole migration (#22).

---

## Phase 4 — Chunking + map pass

**Built:** `app/pipeline/chunk.py` (overlapping page-range planning + token
estimation), `app/pipeline/map_pass.py` (per-chunk structured fact extraction —
dates/amounts/criteria/risk_candidates, each cited to a page), `app/llm/structured.py`
(JSON-schema-enforced LLM output with parse-retry), `app/prompts/map_pass/
v1_map_pass.md`, one Celery task per chunk (not per document, so one chunk's failure
retries only that chunk).

**Problem — user asked for cloud→local resilience:** *"if cloud models are not working
properly turn to ollama local models."* **Fix:** `complete_for_task()` now tries the
Ollama Cloud primary, and on failure (after its own bounded retries) automatically
falls back to a genuinely local Ollama model for the same task, returning which model
actually served the request so provenance stays accurate. Verified end-to-end for
real — forced a genuine primary failure (a nonexistent cloud model tag, a real 404)
and confirmed the local fallback correctly took over (#32).

**Problem — a real map-pass call hung forever with no error:** a real 25-page chunk
sent via `litellm.completion(..., timeout=45)` hung well past 45 seconds with zero
error. Direct reproduction confirmed it: the exact same payload via `requests.post(...,
timeout=X)` against Ollama's native API failed cleanly at exactly X seconds, every
time — litellm simply wasn't enforcing its own timeout for large Ollama prompts. This
was a second, more serious litellm/Ollama gap after Phase 3's image bug, and a direct
violation of the project's own hard rule ("every external call has a timeout"). **Fix:**
bypassed litellm entirely for every Ollama call, text or image — everything now goes
through Ollama's native `/api/chat` via `requests`, whose timeout is actually enforced
(#34).

**Problem — the spec's own suggested chunk size didn't work:** the spec suggested
"~20-30 page chunks." A real 25-page chunk (~17K tokens, real tender text, the real
extraction prompt) never completed even at an 8-minute timeout. A 10-page chunk didn't
complete in 90 seconds. A 3-page chunk completed in 79 seconds. This held on both the
cloud model and the local fallback (which was, if anything, slower) — a genuine
throughput ceiling for this task's complexity, not a network fluke. **Fix:** reduced
`CHUNK_SIZE_PAGES` from 25 to 5 (overlap 2→1), and separately tuned the per-call
timeout up to 180s with only 1 retry (since Celery's own per-chunk task retry is a
second, coarser layer — compounding two aggressive retry counts multiplies worst-case
wait time) (#35, #36).

**Problem — a prompt-templating bug crashed every real call:** `map_pass.py` used
`prompt.format(content=content)`. The prompt's own JSON example
(`{"dates": [...], ...}`) is full of literal `{braces}`, which `.format()` tried to
interpret as placeholders and crashed with `KeyError` on the very first real call.
**Fix:** switched to `.replace("{content}", content)`, and documented the gotcha in
`registry.py` so the three reduce-pass prompts (which have the same JSON-example
shape) wouldn't repeat it in Phase 5 (#37).

**Real validation:** rebuilt chunks for the real 45-page BHEL Catering tender (10
chunks) and ran the map pass on real chunks against live Postgres and live Ollama
Cloud — both succeeded with correctly page-tagged extractions (45 dates, 7 amounts, 13
criteria, 6 risks on one chunk alone), verified directly in the database.

---

## Phase 5 — Reduce pass (go_no_go, synopsis, risk_finder) + citation re-verification

**Built:** `app/pipeline/reduce_pass.py`, three reduce prompts, `app/pipeline/
citation_verify.py`, `app/guardrails/output_checks.py`, `app/services/
analysis_reader.py`, `app/api/routes_analysis.py`, one Celery task per module (not per
document).

**A deliberate design principle, not a bug fix:** the model is asked only for the
genuinely interpretive slice of each module — does this company value satisfy this
criterion; what category is this clause; how should this document be summarized — and
the actual decision/score/severity is computed in code from that narrower output,
never asked of the model directly. Two of the specific rules this produced were
derived from real evidence, not guessed:
- The **company-profile required-fields list** for a real (non-Conditional-Go)
  eligibility check was reverse-engineered from the golden adversarial fixture's own
  ground truth, not assumed (#38).
- The **risk severity rubric** (category → HIGH/MEDIUM/LOW) came directly from the
  golden risk-finder dataset, where the category→severity mapping is 100% consistent
  across every row — real evidence of the intended rubric, not an invented one (#39).
- The **Go/No-Go decision rule** (any failing criterion blocks the whole decision,
  never a weighted average) matches both real rows of the golden go_no_go dataset and
  the project's own zero-hallucination-tolerance rule for eligibility facts (#40).

**Real end-to-end validation surfaced two more real bugs:**
- **A logging crash on Windows:** `run_risk_finder` crashed mid-call the instant a real
  model response contained a non-ASCII character (a typographic hyphen) that
  `logger.warning` tried to print — Windows' default console codepage can't encode it,
  and structlog's PrintLogger doesn't guard against that. Real tender text and real LLM
  prose routinely contain such characters. **Fix:** force UTF-8 stdout at the top of
  `configure_logging()` (#41).
- **Absurd fact duplication in the synopsis:** the same date ("Tender Dated:
  17-06-2019") is genuinely restated on nearly every page of a real tender, and chunk
  overlap multiplies that further — the original dedup key (label, value, page_ref)
  produced 49 near-duplicate `key_dates` entries for what a human would read as ~9
  distinct facts. **Fix:** dedupe on (label, value) only, keeping the first page_ref.
  Re-ran for real after the fix: 49 → 12 (#42).

**Real validation:** ran all three reduce modules for real against the live Catering
document and live Ollama Cloud. The go_no_go result correctly computed `No-Go` from
several genuinely failing criteria; the risk_finder result correctly assigned severity
from the code rubric (not whatever the model guessed); the synopsis correctly declined
to invent a title it couldn't find in the extracted facts and downgraded its own
confidence to "medium" accordingly — exactly the zero-hallucination behavior the spec
requires.

---

## Phase 6 — Guardrails, auth, hardening

**Built:** `app/core/security.py` (JWT + password hashing), `app/api/routes_auth.py`
(`POST /token`), `app/cache/redis_cache.py` (login rate limiting), the full adversarial
eval gate (`evals/test_adversarial.py`, rewritten against the real architecture).

**A real decision that needed asking, not assuming:** the spec's own DDL has no
`users` table, and Tier 2 explicitly excludes full RBAC ("JWT auth only; single
internal bid-team user class"). Adding a per-user table would have been schema beyond
the frozen DDL — exactly what the project's own rules flag as a stop-and-ask trigger.
Asked directly; the user chose a **single shared credential** (one username/password
issuing one JWT, no per-user identity anywhere) over building a new `users` table or
skipping auth entirely (#44).

**Problem — a dependency was silently broken:** `passlib[bcrypt]` crashed at *import
time* with `ValueError: password cannot be longer than 72 bytes` — not a real usage
error, but passlib 1.7.4's own internal self-test failing against the newer `bcrypt`
version pip actually resolves to, since passlib never pinned it. **Fix:** dropped
passlib, called `bcrypt`'s own `hashpw`/`checkpw` directly — the same "route around a
broken library" pattern as the Phase 4 litellm fix (#43).

**Problem — the "is this a tender" guardrail existed but was never actually wired
in:** it had been built in Phase 3 but nothing called it. **Fix:** `validate_upload()`
now runs before any Document row or S3 write — rejects corrupt/0-page PDFs, enforces
the page ceiling, and runs the tender heuristic, all before anything is persisted
(#45).

**Problem found by the rewritten adversarial test, against real fixture content:** a
real non-tender fixture (an annual report) explicitly disclaims tender status in its
own text — *"It is not a tender, solicitation, or notice inviting bids of any kind"* —
and that disclaimer itself contains the words "tender" and "notice inviting," which
defeated the plain substring-match heuristic and produced a false positive on exactly
the case the fixture was built to catch. **Fix:** added a negation-phrase guard,
checked first (#46).

---

## Phase 7 — Performance & cost

**Built:** a two-queue Celery split (`llm` vs `default`, with evidence-based
concurrency settings), explicit timeouts on the S3 and Redis clients, and
`scripts/report_cost.py` (per-document token/request volume reporting).

**Real experiment, not a guess:** fired concurrent real requests at Ollama Cloud to
find out whether the local daemon actually parallelizes cloud calls or just serializes
them. Result: real partial concurrency — 4 concurrent calls finished in 6.6s total
(vs. ~14.8s if fully serial) but each individual call's own latency rose under that
load. This grounded the `llm` queue's `--concurrency=4` setting and the decision to
keep it on a separate worker pool from the cheap, non-LLM chunk-building queue (#47).

**Problem — two more hard-rule-10 gaps:** S3 and Redis calls had no explicit
connect/read timeout, only S3 had retry config. **Fix:** added explicit timeouts to
both (#48).

**The most important finding of this phase — flagged, not hidden:** the spec's own
proposed "<15 minutes p95 for a 500-page document" is **not achievable** at current
free-tier Ollama Cloud throughput. Real measurement — 9 real map-pass calls across 2
real documents, mean ~38 seconds per chunk (range 5.8s-135.5s) — extrapolates to
roughly 20-35 minutes for the map pass *alone* on a 500-page document (125 chunks),
even at the tuned concurrency. The real 372-page NHAI document (93 chunks) already
lands right at ~15 minutes with zero margin, before the reduce pass or any
vision-heavy pages are even counted. This is a spec-level success criterion, not an
internal tuning knob — it was surfaced to the user rather than silently patched or
declared passing (#50).

---

## The pattern behind every fix in this log

Every bug above was found by **running real content through real calls**, not by
inspecting code or trusting a library's documentation:
- Bugs in **litellm** (image handling, timeout enforcement) were found by direct
  request/response reproduction, not litellm's changelog.
- Bugs in **classify.py**/**extract_native.py** (table detection, header detection)
  were found by running the classifier against real, messy government-tender PDFs a
  synthetic fixture set was never going to produce.
- The **chunk-size** and **concurrency** numbers came from timing real calls, not from
  the spec's own suggested figures.
- The **severity rubric** and **required-fields list** came from the golden datasets'
  own ground truth, not from guessing what a domain expert would want.
- The **p95 latency finding** came from extrapolating real measured throughput, and was
  reported honestly even though it means a spec target isn't currently met.

This is also why `docs/DECISIONS.md` exists as a living log rather than a one-time
design doc: nearly every entry past #20 is a *correction*, grounded in a specific,
reproducible, real observation — not a guess made and never revisited.

## Where this leaves the project

Phases 0-7 are built, tested (147 unit/eval tests, ruff+mypy clean, CI green on every
phase), and validated against real tender documents and live infrastructure — not just
mocks. Two things remain openly unresolved, by design, rather than silently patched:

1. **The risk-severity rubric** only covers 5 categories from the golden fixture set —
   a live run found real tender risk categories fell outside it 11 times out of 11 on
   one document. Needs domain-expert review before it can be trusted for real bid
   decisions (see #39's "Revisit if").
2. **The p95 latency target** is not met at current throughput (#50) — a decision for
   the user on how to proceed (accept a revised target, try a faster model, invest in
   a paid tier, or accept "completeness over speed" as the spec's own stated priority).

Phase 8 (observability, frontend, ship) is next: Langfuse tracing through every
pipeline stage, Prometheus+Grafana, `docs/RUNBOOK.md` filled in for real, and the
Next.js frontend with the citation-click UI that is this project's actual HITL
mechanism.
