# GenAI Project Build Kit
### The executable companion — turn the playbook into a project a coding agent can actually build

---

## How the three documents fit together

| Document | What it is | When you open it |
|---|---|---|
| **FastAPI + ML Production Playbook** | Engineering reference — folder structure, auth, testing, caching, Docker, Prometheus, deployment mechanics | When you need the *how* of a specific engineering task |
| **GenAI + Agentic AI Production Playbook** | Design & risk audit checklist (SANE-AI) — what to think about, what can go wrong | At kickoff (Layer S), and again before you ship (full audit) |
| **This document — Build Kit** | The executable layer: project spec template, tier scoping, repo scaffold, phase-gated build order, and the `CLAUDE.md` you hand to a coding agent | Every new project, start to finish |

The playbook tells you *what good looks like*. This tells you *what to do on Monday morning, and what to type into Claude Code.*

---

# PART 1 — Project Tiers (do this first, it saves you weeks)

The single biggest practical problem with a 25-section production checklist is that **most projects don't need all of it**, and trying to apply all of it to a two-week portfolio project guarantees you ship nothing. Pick a tier before you start.

| | **Tier 1 — Portfolio / Demo** | **Tier 2 — Internal / Pilot** | **Tier 3 — External / Production** |
|---|---|---|---|
| **Users** | You, interviewers, a demo audience | A known internal team | Real external users / customers |
| **Blast radius if wrong** | Embarrassment | Bad internal decision | Financial, legal, reputational |
| **Typical timeline** | 1–3 weeks | 1–3 months | 3+ months, ongoing |
| **Layer S (Scope)** | ✅ Required — full | ✅ Required — full | ✅ Required — full |
| **Layer A (Architecture)** | ✅ Required — full | ✅ Required — full | ✅ Required — full |
| **Layer N (RAG/Reasoning)** | ✅ Required — full | ✅ Required — full | ✅ Required — full |
| **Evaluation (§13)** | ✅ **Required** — 30 examples min | ✅ Required — 100+ | ✅ Required + CI-gated |
| **Tracing/observability (§19)** | ✅ **Required** — LangSmith free tier | ✅ Required | ✅ Required + alerting |
| **Testing (§14)** | ✅ Unit + integration | ✅ + E2E | ✅ + load tests |
| **Auth (FastAPI Ph.5)** | 🟡 API key only | ✅ JWT/OAuth | ✅ Full + RBAC |
| **Caching (§18)** | 🟡 If cost is a problem | ✅ Required | ✅ + semantic caching |
| **Cost/FinOps (§17)** | 🟡 Token caps only | ✅ Required | ✅ + budget alerts |
| **Guardrails/safety (§15)** | 🟡 Output validation only | ✅ + injection tests | ✅ Full + scheduled red-team |
| **Data governance (§16)** | ⬜ Skip | ✅ Required | ✅ + deletion guarantees |
| **HITL (§20a)** | ⬜ Skip | 🟡 If high-stakes output | ✅ Required |
| **Drift monitoring (§19)** | ⬜ Skip | 🟡 Quarterly manual | ✅ Automated |
| **Layer X (systemic resilience)** | ⬜ Skip | 🟡 Read once, apply 2–3 | ✅ Full |
| **Multi-tenancy isolation** | ⬜ Skip | ✅ If multi-user | ✅ Required |
| **Exit strategy (§22)** | ⬜ Skip | 🟡 | ✅ Required |

✅ required · 🟡 judgment call · ⬜ skip, and *say in your README that you skipped it deliberately*

> **Why the Tier 1 "required" column still includes evaluation and tracing:** those two are what separate a project you can *defend* from a demo you can only *show*. If you can't answer "how do you know it works?" and "why did it answer that?", the project doesn't demonstrate engineering judgment — and those are the two questions that get asked hardest in interviews.

---

# PART 2 — The Project Spec

Fill this in **before any code**. Budget 30–45 minutes. This becomes `docs/SPEC.md` in your repo and is the primary context you hand to a coding agent.

```markdown
# <Project Name> — Spec

## 1. Responsibility (1–2 sentences)
This system <does X> for <whom>, using <what data>.
It does NOT <the nearest adjacent thing it's easy to assume it does>.

## 2. Tier
Tier: <1 / 2 / 3>
Deliberately skipped: <list, per the tier table>

## 3. Behavior mode
[ ] Advisory — surfaces information, human decides
[ ] Autonomous — takes action without per-action approval
Irreversible outputs: <list, or "none">

## 4. Users & domain
Primary user + their expertise level:
In-domain questions (3 examples):
Out-of-domain questions it must refuse (3 examples):
Out-of-domain behavior: <refuse / redirect / escalate>

## 5. Inputs
| Modality | Source | Volume | Limits | Validation |
|---|---|---|---|---|
| e.g. PDF | user upload | ~200 docs | 20MB, 100pg | type + size + page count |

## 6. Outputs
Format: <prose / JSON / report>
Schema (if structured): <paste the Pydantic model>
Must include: [ ] confidence  [ ] citations  [ ] "I don't know" path

## 7. Hallucination tolerance
Level: <zero / low / acceptable>
Rationale:
What happens when the system isn't sure:

## 8. Success criteria
| Metric | Target | How measured |
|---|---|---|
| Answer accuracy | e.g. ≥85% on eval set | LLM-as-judge + manual spot check |
| Retrieval recall@5 | e.g. ≥90% | eval set, retrieval measured separately |
| p95 latency | e.g. <5s | Locust |
| Cost/query | e.g. <₹2 | token accounting |

## 9. Scale & budget
Expected queries/day:        Peak concurrency:
Monthly cost ceiling:        Latency SLO:

## 10. Architecture decision
[ ] Pipeline (no agent)  [ ] Single agent + tools  [ ] Multi-agent
Rationale — why NOT the simpler option:

## 11. Key assumptions (and what breaks if wrong)
| Assumption | If false, then... | Runtime check? |
|---|---|---|

## 12. Explicitly out of scope (v1)
```

### The Decision Log — mandatory, and not just for tidiness

Keep `docs/DECISIONS.md` and add a row **every time you make a technical choice**:

| # | Decision | Options considered | Chose | Why | Revisit if |
|---|---|---|---|---|---|
| 1 | Vector store | FAISS, Chroma, Pinecone, pgvector | pgvector | Already running Postgres; <100k chunks; avoids a second service | Chunk count >500k or need hybrid search |
| 2 | Chunk size | 256/512/1024 tokens | 512, 15% overlap | Manual eval on 20 queries: 512 beat 256 on recall, matched 1024 at lower cost | Recall@5 drops below 85% |

This is the single highest-leverage habit in this kit. It costs two minutes per decision and it's what converts "I built a RAG chatbot" into "I chose pgvector over Pinecone because X, and here's the measurement that justified my chunk size." When a coding agent makes the choice for you, **you still write the row** — that's the difference between having a project and being able to defend one.

---

# PART 3 — Reference Repository Scaffold

Extends the FastAPI playbook's structure with the GenAI-specific layers. Create this skeleton before writing logic.

```
project/
├── app/
│   ├── main.py                     # app assembly: routes, middleware, lifespan
│   ├── api/
│   │   ├── routes_chat.py          # /chat, /query — streaming (SSE)
│   │   ├── routes_ingest.py        # /ingest — document upload
│   │   ├── routes_feedback.py      # /feedback — thumbs, corrections
│   │   └── routes_health.py        # /health, /ready
│   ├── core/
│   │   ├── config.py               # pydantic-settings, all env vars
│   │   ├── security.py             # auth (API key / JWT)
│   │   ├── dependencies.py         # DI: session, current_user, clients
│   │   ├── exceptions.py           # centralized handlers + failure taxonomy
│   │   └── logging.py              # structured logging config
│   ├── llm/
│   │   ├── client.py               # LiteLLM wrapper — THE ONLY place a provider is named
│   │   ├── router.py               # fast vs accurate model routing
│   │   └── structured.py           # structured-output enforcement + retry
│   ├── prompts/
│   │   ├── system/v1_system.md     # versioned as FILES, not inline strings
│   │   ├── planner/v1_planner.md
│   │   └── registry.py             # loads by name+version, logs which was used
│   ├── rag/
│   │   ├── ingest.py               # load → clean → dedupe → chunk → embed → upsert
│   │   ├── chunking.py             # per-modality strategies
│   │   ├── retrieve.py             # search + rerank + assemble context
│   │   └── store.py                # vector store adapter (swappable)
│   ├── agents/
│   │   ├── graph.py                # LangGraph definition
│   │   ├── state.py                # explicit agent state (Pydantic) — no hidden memory
│   │   └── tools/                  # one file per tool, each with schemas
│   ├── memory/
│   │   ├── session.py              # conversation history, scoped per session/tenant
│   │   └── summarize.py            # history compaction when context fills
│   ├── guardrails/
│   │   ├── input_checks.py         # sanitization, injection heuristics
│   │   └── output_checks.py        # schema, PII, confidence threshold
│   ├── services/                   # business logic, orchestrates the above
│   ├── middleware/
│   │   └── logging_middleware.py
│   ├── cache/
│   │   └── redis_cache.py          # embeddings, retrieval, semantic response cache
│   └── models/                     # SQLAlchemy ORM + Pydantic schemas
├── evals/
│   ├── datasets/golden.jsonl       # the eval set — version-controlled
│   ├── test_retrieval.py           # retrieval metrics, measured ALONE
│   ├── test_generation.py          # faithfulness, accuracy
│   └── test_adversarial.py         # injection, out-of-domain, ambiguous
├── tests/
│   ├── unit/                       # LLM + vector store mocked
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── SPEC.md                     # Part 2 of this kit
│   ├── DECISIONS.md                # the decision log
│   ├── ARCHITECTURE.md             # diagram + data flow
│   └── RUNBOOK.md                  # known failures + what to do
├── scripts/
│   ├── ingest_corpus.py
│   └── build_eval_set.py
├── CLAUDE.md                       # ← Part 5: standing rules for the coding agent
├── docker-compose.yml              # api + postgres + redis + prometheus + grafana
├── Dockerfile
├── prometheus.yml
├── .env.example                    # committed; .env is NOT
└── README.md
```

**Three structural rules worth internalizing:**
1. `app/llm/client.py` is the *only* file that names a provider. If `openai` or `gemini` appears anywhere else, "swap the model in a day" is already false.
2. Prompts are **files with versions**, not strings inside Python. You cannot diff, review, or bisect an inline f-string.
3. `evals/` sits beside `tests/`, not inside it. Tests answer "is it broken?" Evals answer "is it good?" They run on different cadences and fail for different reasons.

---

# PART 4 — Build Order with Phase Gates

Do not start a phase until the previous gate passes. Each phase is a natural unit of work to hand a coding agent.

### Phase 0 — Spec & scaffold
**Build:** `docs/SPEC.md`, repo skeleton, `.env.example`, `docker-compose.yml` with Postgres + Redis, `/health` endpoint, CI that runs lint + an empty test suite.
**Gate:** `docker-compose up` works, `/health` returns 200, CI is green.

### Phase 1 — Eval set FIRST
**Build:** 30–50 examples in `evals/datasets/golden.jsonl` before building the thing they evaluate.

```jsonl
{"id":"q001","question":"...","expected_facts":["...","..."],"source_doc":"manual_v3.pdf#p12","category":"specs","difficulty":"easy"}
{"id":"q014","question":"<ambiguous phrasing>","expected_behavior":"ask_clarification","category":"ambiguous"}
{"id":"q022","question":"<out of domain>","expected_behavior":"refuse","category":"ood"}
```

Composition: ~60% normal in-domain, ~20% hard/edge, ~10% out-of-domain (must refuse), ~10% ambiguous (must clarify).
Sources: real user questions if you have them; otherwise write them from the source documents and have someone who knows the domain sanity-check.
**Gate:** the eval set exists, is committed, and you can run it (it will fail — that's fine, there's nothing to test yet).

### Phase 2 — Ingestion & retrieval, measured alone
**Build:** `app/rag/` — loaders, cleaning, dedupe, chunking, embedding, upsert. Plus `scripts/ingest_corpus.py` and a retrieval-only eval.

Starting parameters (tune from here, don't accept blindly):
- Prose/PDF: 512 tokens, 10–15% overlap, split on structure (headings → paragraphs → sentences) before falling back to characters
- Tables: keep row groups intact; store the header with every chunk or the rows are meaningless
- Transcripts: split on speaker turns + time windows
- Code: function/class level
- Always store metadata: `source`, `page`/`section`, `timestamp`, `doc_version`

**Gate:** `recall@5 ≥ 85%` on your eval set, **measured on retrieval alone with no LLM involved.** This is the most commonly skipped gate and the most expensive to skip — if retrieval is at 60%, no amount of prompt engineering downstream will fix the answers, and you'll spend a week blaming the model.

### Phase 3 — Generation, single-turn
**Build:** `app/llm/client.py` (LiteLLM), prompt registry, structured output enforcement, one `/query` endpoint. No agent yet. No conversation history yet.
**Gate:** faithfulness + accuracy targets met on the eval set; every answer carries citations; the "I don't know" path fires correctly on out-of-domain questions.

### Phase 4 — Conversation & memory
**Build:** `app/memory/` — session history scoped per session and tenant, history compaction when context fills, multi-turn eval cases.
**Gate:** multi-turn eval passes; no cross-session leakage (test this explicitly with two concurrent sessions).

### Phase 5 — Agent & tools *(skip entirely if your spec said "pipeline")*
**Build:** `app/agents/` — LangGraph, explicit Pydantic state, tools with schemas, allowlist, loop detection, step caps, cooldowns.
**Gate:** agent traces are readable in LangSmith/Langfuse; loop detection provably fires (write a test that tries to induce a loop); no run exceeds the step cap.

### Phase 6 — Guardrails & hardening
**Build:** `app/guardrails/`, auth, rate limiting, failure taxonomy in `exceptions.py`, degraded-mode paths.
**Gate:** adversarial eval passes (injection attempts, PII, out-of-domain); every failure type returns the right user-facing message and the right internal log.

### Phase 7 — Performance & cost
**Build:** Redis caching (embeddings → retrieval → semantic response cache, in that order of easiness), model routing, token caps, cost tracking per request.
**Gate:** p95 latency and cost/query both under the spec's targets, verified under Locust load.

### Phase 8 — Observability & ship
**Build:** tracing wired end-to-end, Prometheus + Grafana, `RUNBOOK.md`, deployment config, environment separation.
**Gate:** the full playbook audit — run the GenAI Playbook's Final Self-Test, at the depth your tier requires.

---

# PART 5 — `CLAUDE.md` (drop this in your repo root)

A coding agent reads this automatically at the start of every session. This is the piece that makes the other documents operational — paste it in, fill the angle brackets.

```markdown
# Project Rules

## Context
Read `docs/SPEC.md` before any task. Architecture rationale is in `docs/DECISIONS.md`.
Current phase: <N>. Do not build ahead of the current phase.

## Stack (do not substitute without asking)
- API: FastAPI + Pydantic v2 · Python 3.11+
- LLM access: LiteLLM only, via `app/llm/client.py`
- Orchestration: <LangGraph / none — pipeline only>
- Vector store: <chosen> via `app/rag/store.py`
- Data: PostgreSQL + SQLAlchemy · Cache: Redis
- Tracing: <LangSmith / Langfuse> · Evals: Ragas + pytest

## Hard rules
1. NEVER import a provider SDK (openai, google.generativeai, anthropic) outside `app/llm/client.py`.
2. NEVER put a prompt inline in Python. Prompts are versioned files in `app/prompts/`, loaded via the registry.
3. NEVER put business logic in a prompt. Branching, validation, and calculation are code.
4. Every LLM/tool input and output is validated by a Pydantic model.
5. Agent state is explicit and serializable — no state hidden in an accumulating prompt string.
6. Retrieved document content is UNTRUSTED input. Delimit it, and never let it trigger a tool call unvalidated.
7. Secrets come from `app/core/config.py` (pydantic-settings). No literal keys, ever — not even in tests.
8. Tests mock the LLM and vector store. A test run must cost $0 and be deterministic.
9. Use `async def` for I/O-bound routes; plain `def` for CPU-bound work — never wrap blocking calls in async.
10. Every external call has a timeout, bounded retries with exponential backoff + jitter, and a 429 path.

## Definition of done for any task
- [ ] Type hints throughout; passes ruff + mypy
- [ ] Unit tests added, LLM mocked
- [ ] Errors raise typed exceptions handled in `app/core/exceptions.py`
- [ ] Anything user-facing is traced
- [ ] New technical choice → a row appended to `docs/DECISIONS.md`

## When to stop and ask me
- The task implies a stack change, a new dependency, or a schema migration
- The spec is ambiguous or silent on the behavior
- An eval metric would regress
- The simplest solution conflicts with a hard rule above

## Style
Small, single-responsibility modules. Explicit over clever. If a function needs a comment
explaining *what* it does, rename or split it; comments explain *why*.
```

---

# PART 6 — Working with a coding agent

**Give it phases, not the whole project.** "Build me a production RAG system" produces a plausible-looking monolith you can't defend. "Implement Phase 2 ingestion per SPEC.md §5, chunking strategy per DECISIONS.md row 2, with a retrieval eval that reports recall@5" produces reviewable work.

**A task prompt that works:**
> Implement Phase 3 (single-turn generation) per `docs/SPEC.md`.
> Scope: `app/llm/client.py`, `app/prompts/system/v1_system.md`, `app/prompts/registry.py`, `app/api/routes_chat.py`, plus unit tests.
> Constraints: CLAUDE.md hard rules apply. Citations required in every response. Out-of-domain questions must hit the refusal path.
> Do not touch `app/rag/` — Phase 2 is closed.
> When done, run `pytest evals/test_generation.py` and report the metrics. Don't fix failures yet — show me the numbers first.

**Three habits that matter more than the prompt:**
1. **Close phases.** Explicitly telling it which directories are off-limits prevents the quiet rewrite of working code.
2. **Ask for numbers before fixes.** "Report the metrics, don't fix" stops it from tuning prompts until the eval passes, which is how you get a system that's overfit to 40 examples.
3. **Interrogate every non-trivial choice before you merge it** — "why this chunk size, what else did you consider, what would change your mind?" If you can't reproduce the answer in your own words a week later, the decision isn't yours yet and it won't survive a follow-up question from anyone else.

---

# PART 7 — Cross-check: gaps none of the three documents covered

I re-read the FastAPI playbook and the GenAI playbook against this build order. These were genuinely missing from both, and are now in the kit above:

| Gap | Where it's fixed |
|---|---|
| **Tier scoping** — both playbooks implied every project needs everything | Part 1 |
| **Document ingestion pipeline** — both covered retrieval, neither covered loading, cleaning, deduplication, incremental updates, or reindexing | Phase 2 + `app/rag/ingest.py` |
| **Concrete chunking parameters** — "define a strategy per modality" with no starting numbers | Phase 2 |
| **Retrieval measured independently of generation** — the highest-value debugging practice in RAG, absent from both | Phase 2 gate |
| **How to actually build a golden dataset** — both said "create one," neither said size, composition, or format | Phase 1 |
| **Conversation/session memory** — both discussed agent state, neither covered multi-turn history, compaction, or per-session scoping | Phase 4 + `app/memory/` |
| **Structured output enforcement** — validation was covered; *getting* valid JSON out of an LLM (native structured output / function calling, with parse-failure retry) wasn't | `app/llm/structured.py` |
| **Provider rate limits & 429 handling** — the FastAPI doc covered rate-limiting *your* API, neither covered being rate-limited *by* the LLM provider | CLAUDE.md rule 10 |
| **Prompt injection via retrieved content** — injection was named as a risk; the RAG-specific vector (untrusted document text reaching the model as if it were instruction) wasn't | CLAUDE.md rule 6, Phase 6 |
| **Cost estimation method** — "estimate cost per request" with no formula | Below |
| **Build sequencing** — both were checklists with no order; neither said what to build first or when a phase is done | Part 4 |
| **Eval vs. test distinction** — conflated in both; they fail differently and run on different cadences | Part 3, rule 3 |

**Cost estimate formula** (run this at Phase 0, not after the first bill):

```
per query   = (in_tokens × in_price) + (out_tokens × out_price)
              + (retrieval_k × chunk_tokens × in_price)      ← the line people forget
monthly     = per_query × queries/day × 30 × (1 − cache_hit_rate)
one-time    = total_corpus_tokens × embedding_price          ← × every reindex
```

Retrieved context is usually the *largest* input cost in a RAG system — a k=5 retrieval at 512 tokens/chunk adds ~2,500 input tokens to every single query, often several times the user's actual question. This is also why retrieval caching pays for itself faster than response caching.

---

## Quick start for the next project

1. Fill `docs/SPEC.md` (Part 2) — 45 minutes
2. Pick your tier (Part 1) — 5 minutes, and write down what you're skipping
3. Scaffold the repo (Part 3), drop in `CLAUDE.md` (Part 5)
4. Build the eval set (Phase 1) **before** the thing it evaluates
5. Work Phase 2 → 8, one at a time, gate by gate
6. Before shipping: run the GenAI Playbook's Final Self-Test at your tier's depth

*Companion to: FastAPI + ML Production Playbook · GenAI + Agentic AI Production Playbook. Stack references current as of September 2026 — re-check agent frameworks and observability tooling every few months.*
