# GenAI + Agentic AI Production Playbook
### The SANE-AI design framework + the FastAPI engineering playbook, merged into one build order — with a named production stack for every layer

---

## How this document was built

You gave me two things to combine:

1. **Your GenAI application checklist** — the SANE-AI framework (Scope → Architecture → Normalization → Evolution, plus a Development & Delivery layer you'd started adding). This is the strongest *design and risk* checklist I've seen for LLM/agentic systems — it tells you **what to think about**.
2. **The FastAPI + ML Production Playbook** we built earlier — this tells you **how to actually build and ship it**: project structure, auth, testing, caching, monitoring, deployment.

They weren't competing — one is the architecture-and-risk layer, the other is the engineering-and-serving layer for the same system. This document merges them: the SANE-AI layers are the spine, and wherever a SANE-AI checklist item is really an engineering task (auth, caching, testing, monitoring, deployment), the FastAPI playbook's concrete implementation is folded in directly instead of living in a separate file you'd have to cross-reference.

I also did two things you asked for specifically:
- **Every major checklist item now has a "Stack" line** — the actual widely-used production options for that job, tagged by use case (prototype vs. production, managed vs. self-hosted), not just the concept.
- **Consolidated the repeated "missing gaps" waves** from your original doc (there were four separate rounds of "here's what's still missing") into the layers they actually belong to, so this is one linear checklist instead of a checklist plus three addenda.

> **Revision note:** On audit, the first pass had real gaps — a broken cross-reference to a "Prompt Management" section that didn't exist, plus several checklist items from your original doc that got summarized away rather than carried over (Model Strategy, agent state/memory, user intent ambiguity handling, recovery from partial failure, human-in-the-loop workflow, documentation & maintenance, system humility, cognitive load). All are now added inline, marked **[Added]**.

---

## Tech Stack Legend — read this once, then use it as a reference

A single "best" tool rarely exists — it depends on whether you're prototyping, shipping a portfolio project, or building for enterprise scale. This table is the decision key the rest of the document points back to.

| Layer | Prototype / Learning | Production (small-mid team) | Production (enterprise scale) | Notes |
|---|---|---|---|---|
| **Agent orchestration** | LangChain (simple chains) | **LangGraph** — graph-based state machine, best error handling, human-in-the-loop support | LangGraph or Microsoft Agent Framework (AutoGen's successor — AutoGen itself is now in maintenance mode) | **You already use LangChain/LangGraph** — this is the right call; LangGraph has the highest published task-completion rate on complex multi-step workflows of the mainstream frameworks |
| **Multi-agent (role-based teams)** | CrewAI | CrewAI (2B+ agent executions/yr in production as of 2026) or LangGraph sub-graphs | CrewAI + LangGraph hybrid (LangGraph controls the flow, CrewAI crews handle autonomous sub-tasks) | Use multi-agent only when the problem genuinely maps to specialist roles — most use cases need one well-tooled agent, not a crew |
| **Type-safe minimal agents** | PydanticAI | PydanticAI | — | Worth knowing — newer, minimal, built directly on Pydantic (which you already use in FastAPI schemas) |
| **Tool/connector standard** | **MCP (Model Context Protocol)** | MCP | MCP | **You already use MCP** — it's become the standard way to expose tools/data sources to agents instead of hand-rolled function-calling wrappers |
| **LLM provider abstraction** | Direct SDK calls (OpenAI, Gemini) | **LiteLLM** — unified interface across providers, enables the "swap model in a day" requirement | LiteLLM Proxy or a custom gateway with routing/fallback | Never hard-code a single provider's SDK into business logic — this is SANE-AI's own Model Strategy requirement |
| **Vector DB** | FAISS (local, free, no infra) or ChromaDB | **Pinecone** (managed, easiest ops) or **Qdrant** (self-hosted, fast, Rust-based) | Weaviate (hybrid search + k8s-native) or Milvus (largest scale) | **You already use FAISS/Pinecone/ChromaDB** — FAISS for local dev/experiments, Pinecone when you need a managed production service without running infra yourself |
| **Structured/relational data** | SQLite | PostgreSQL (+ `pgvector` if you want vectors and relational data in one place) | PostgreSQL + read replicas | If your vector needs are modest, `pgvector` avoids running a second database entirely |
| **Embeddings** | OpenAI `text-embedding-3-small`, Gemini embeddings | Same, chosen and justified per SANE-AI's own Section 10 requirement | Self-hosted (BGE, E5) when cost/data-residency demands it | Never pick an embedding model by default — document *why* |
| **Observability / tracing** | **LangSmith** (native to LangChain/LangGraph, easiest setup) | LangSmith if LangGraph-native, else **Langfuse** (open-source, self-hostable, framework-agnostic) | Langfuse self-hosted or Arize Phoenix (OTel-native, strong RAG drift detection) | **You already use LangSmith** — good default since you're on LangChain/LangGraph; keep Langfuse in mind if you ever need self-hosting for data residency |
| **Evaluation / regression testing** | Ragas (RAG-specific metrics) | Ragas + DeepEval (pytest-style LLM unit tests) | Same + promptfoo in CI for prompt regression gating | This is what makes "golden dataset" and "regression tests for prompt changes" (SANE-AI §13) actually executable |
| **Guardrails / safety** | Guardrails AI (schema + validation) | NeMo Guardrails (conversational rails) or Guardrails AI | NeMo Guardrails + Microsoft Presidio (PII detection/redaction) | Presidio specifically covers SANE-AI's "sensitive data redaction" item |
| **Prompt-injection / red-teaming** | Manual adversarial prompts | promptfoo redteam module | Garak (NVIDIA's LLM vulnerability scanner) + scheduled red-team runs | Covers SANE-AI's Security layer directly |
| **Caching** | In-memory dict | **Redis** (same as your FastAPI stack) | Redis + GPTCache (semantic caching layer purpose-built for LLM responses) | You already have Redis from the FastAPI playbook — reuse it for embedding/retrieval/response caching here too |
| **API serving layer** | FastAPI, `uvicorn --reload` | **FastAPI** + Gunicorn/Uvicorn workers | FastAPI behind a gateway (Kong/AWS API Gateway) | This is your existing FastAPI playbook, unchanged |
| **Self-hosted model serving** | Ollama (local dev) | vLLM or TGI (Text Generation Inference) | vLLM with autoscaling on GPU nodes | Only relevant if you're not calling a hosted API |
| **Containerization** | Docker + `docker-compose` | Docker + `docker-compose` | Kubernetes | Same as the FastAPI playbook |
| **Infra monitoring** | — | **Prometheus + Grafana** (same as FastAPI playbook) | Same, + Datadog if already standardized org-wide | Infra metrics (latency, error rate, resource use) — complements, doesn't replace, LLM-specific tracing |
| **Secrets management** | `.env` file | `.env` + `pydantic-settings` (local), platform secret store in prod | HashiCorp Vault or cloud-native secret manager (AWS Secrets Manager / GCP Secret Manager) | `.env` is fine for dev; never for production secrets at scale |
| **Feature flags** | Hardcoded booleans | Unleash (open-source) | LaunchDarkly | Needed for SANE-AI's canary/rollback requirements |

---

## Layer S — Scope & Responsibility
*"What is this system allowed to do — and not do?"*

### 1. Problem Definition
- [ ] System responsibility written in 1–2 sentences
- [ ] Advisory (decision-support) vs. autonomous (decision-making) behavior explicitly chosen
- [ ] Domain boundaries listed — what's in scope, what isn't
- [ ] Out-of-domain behavior defined (refuse? redirect? escalate?)
- [ ] Irreversible outputs identified — anything the system says that can't be "taken back" (financial guidance, medical/legal interpretation) gets flagged for extra scrutiny later

### 2. Assumptions & Constraints
- [ ] Key assumptions documented explicitly (e.g., "users ask clear questions," "retrieved documents are correct," "OCR confidence > threshold") — most GenAI failures are assumption violations, not bugs
- [ ] Assumptions validated at runtime where feasible, with alerts when they break
- [ ] Fallback behavior defined for when an assumption fails
- [ ] Hallucination tolerance defined: zero / low / acceptable, and where on that spectrum each part of the system sits

### 3. Input Contracts
- [ ] All input modalities listed (text/image/audio/video/docs/tables)
- [ ] Input validation rules and size/length/quality limits enforced — **Stack:** Pydantic `Field` constraints (same pattern as the FastAPI playbook's Phase 2) at the API boundary, before anything touches the model
- [ ] Metadata captured (user role, timestamp, source)
- [ ] Input routing logic is deterministic code, not LLM-guessed
- [ ] Input sanitization per modality (this is also a security control — see Layer E §15)

### 4. Output Contracts
- [ ] Output format explicitly defined (text / JSON / report) — **Stack:** Pydantic response schemas, same discipline as the FastAPI playbook's model I/O schema design
- [ ] Structured schema enforced where applicable
- [ ] Confidence/uncertainty exposed in the response
- [ ] Citations/sources included where the output makes a factual claim
- [ ] An explicit "I don't know" path is designed, not left as an emergent LLM behavior

---

## Layer A — Architecture & Orchestration
*"How decisions flow through the system"*

### 5. Architecture Choice
- [ ] Pipeline vs. Agent vs. Hybrid chosen **intentionally**, not by default
- [ ] Agent used only where actual decisions/branching are required — deterministic steps (parsing, formatting, DB writes) stay as plain code, not agent reasoning
- [ ] Max agent steps defined
- [ ] Termination conditions enforced (see §11 for the specifics — loop detection, cooldowns, forced termination)

**Stack:** LangGraph for anything with real state/branching; a plain pipeline (FastAPI route → function → function) for anything that doesn't need agentic reasoning at all. Don't reach for an agent framework by default — SANE-AI's own principle is "agent used only where decisions are required."

### 6. Capability Decomposition
- [ ] Input parsing isolated as its own step
- [ ] Understanding (OCR/ASR/etc.) isolated from reasoning
- [ ] Context construction isolated
- [ ] Reasoning isolated
- [ ] Action execution isolated
- [ ] Response generation isolated

This maps directly onto the FastAPI playbook's service-layer separation (`app/services/`, `app/api/`) — each capability above is its own module/service, not logic tangled inside a single route handler.

### 7. Tooling & Agents
- [ ] Each tool documented with: name, description, input schema, output schema, failure modes
- [ ] Tool allowlist enforced — the agent can't call anything not explicitly registered
- [ ] Tool inputs/outputs schema-validated (Pydantic again)
- [ ] Tools fail gracefully — timeouts configured, retries limited, external API rate limits handled (**this is the FastAPI playbook's "tools can fail gracefully" concern, applied to LLM tool calls instead of REST calls**)
- [ ] Tool cooldown / repetition detection in place (prevents an agent from calling the same tool in a loop)
- [ ] Agent loop detection implemented

### 7a. Model Strategy — **[Added, was missing]**
- [ ] Model calls abstracted behind a single interface — no route or service calls a provider SDK directly
- [ ] No hard-coded provider logic anywhere in business logic ("never marry a model" — your own doc's words)
- [ ] Fallback model defined for when the primary provider errors or times out
- [ ] Cost per request estimated per model choice
- [ ] Model routing rules defined — fast/cheap model for simple queries, accurate/expensive model for hard ones

**Stack:** LiteLLM is built exactly for this — one interface, provider-agnostic, with routing and fallback built in. This is what makes "swap the LLM in a day" (your own Final Self-Test question) actually true instead of aspirational.

### 8. Decision Traceability
- [ ] Why a retrieval was or wasn't performed — logged
- [ ] Why a specific tool was selected — logged
- [ ] Why clarification was or wasn't asked — logged
- [ ] Full decision timeline reconstructable from logs
- [ ] **[Added]** Explicit agent state maintained as structured data (JSON), not implicitly carried inside a growing prompt string
- [ ] **[Added]** No hidden memory inside prompts — anything the agent "remembers" between steps should be visible in the logged state, not silently baked into an ever-growing context window where you can't audit what it actually knows

**Stack:** This is exactly what LangSmith/Langfuse tracing gives you natively when the agent runs through LangGraph — every node, tool call, and decision point is captured as a span without you hand-rolling a logging schema. "The answer is wrong" is useless without a reconstructable decision path.

---

## Layer N — Normalization & Reasoning
*"Reduce chaos before intelligence"*

### 9. Multimodal Normalization
- [ ] All modalities normalized to text + metadata before reasoning
- [ ] Modality confidence tracked per input
- [ ] Cross-modal conflict detection (image says A, text says B — what wins?)
- [ ] Conflict resolution strategy defined, with disagreement surfaced to the user rather than silently picked
- [ ] **[Added]** A clear, low-effort path exists to add a new modality later (a new normalizer that outputs the same text+metadata shape) without rewriting the reasoning layer

### 10. Context & RAG
- [ ] Chunking strategy defined **per modality** — a PDF, a transcript, and a table need different chunking logic
- [ ] Embedding model chosen and justified (see Stack Legend above)
- [ ] Vector DB used only where semantic search is actually needed — structured/tabular data stays in a relational store, not force-fit into vectors
- [ ] Retrieval ranking strategy defined (pure similarity vs. hybrid search vs. re-ranking)
- [ ] Context window management implemented — don't just stuff everything in and hope
- [ ] Source attribution preserved end-to-end, from retrieval through to the final citation shown to the user

**Stack:** LlamaIndex for retrieval-heavy pipelines (its ingestion/chunking/retrieval tooling is more mature specifically for RAG); LangChain/LangGraph when RAG is one step inside a broader agentic flow. Pinecone/Qdrant/Weaviate per the legend above depending on managed-vs-self-hosted needs. If the app also needs conventional records (users, chat history, feedback), that's a normal Postgres/SQLAlchemy layer — reuse the FastAPI playbook's Phase 3 pattern (`database.py`/`models.py`/`schemas.py`/`crud.py`) rather than inventing a new one.

### 11. Reasoning Control
- [ ] **[Expanded — this was a dangling reference to a section that didn't exist; the full original "Prompt Management" checklist is folded in here instead]** Prompts versioned, with system / planner / tool prompts kept as separate, independently-versioned artifacts — not one giant string
- [ ] Prompt changes tracked (git, or a prompt-management tool) so a regression can be bisected to a specific edit
- [ ] Prompts evaluated before deployment (ties to §13's regression testing)
- [ ] No business logic embedded inside prompts — branching/validation/calculation stays in code, the prompt stays a prompt
- [ ] Reasoning depth capped
- [ ] Non-determinism controlled — deliberate temperature bands, not defaults left untouched
- [ ] A deterministic mode available for audits and debugging (fixed seeds where the provider supports them)
- [ ] "Give up" criteria defined — the agent has a defined point where it stops and escalates instead of looping

### 11a. User Intent & Ambiguity Handling — **[Added, was missing]**
- [ ] Intent confidence scoring — the system estimates how clear the user's request actually is
- [ ] Ambiguity detection, separate from low-confidence *answers* — a clear question with an uncertain answer is a different failure mode from an unclear question
- [ ] A clarification-first policy for low-intent-confidence input, with a defined safe default when clarification isn't possible

LLMs confidently answer the wrong question at least as often as they get the right question wrong — this is worth designing for explicitly, not leaving to emergent behavior.

### 12. Domain & Temporal Awareness
- [ ] Domain scope enforced at the reasoning layer, not just documented in Layer S
- [ ] Out-of-domain detection implemented
- [ ] Data timestamps preserved through retrieval
- [ ] Freshness constraints enforced (don't answer 2026 questions from 2022 documents without flagging it)
- [ ] Temporal disclaimers shown to the user when relevant

---

## Layer E — Evolution & Operations
*"Can this system survive reality?"*

This layer is where the FastAPI playbook does most of the heavy lifting — testing, caching, monitoring, and deployment are engineering disciplines, not GenAI-specific ones, and the practices transfer directly.

### 13. Evaluation & Quality
- [ ] Golden dataset created and maintained
- [ ] Offline evaluation pipeline exists — **Stack:** Ragas for RAG-specific metrics (faithfulness, relevance), DeepEval for pytest-style assertions on LLM outputs, run in CI the same way the FastAPI playbook runs `pytest tests/`
- [ ] Metrics defined and tracked: faithfulness, accuracy, latency, cost, robustness
- [ ] Regression tests for prompt changes — **Stack:** promptfoo in CI, so a prompt edit that degrades quality is caught before merge, exactly like a code regression test
- [ ] Adversarial test cases included
- [ ] Drift detection in place (see §19)

### 14. Testing (engineering layer — from the FastAPI playbook, applied here)
- [ ] **Unit tests** — business logic, schema validators; fast, no external calls
- [ ] **Integration tests** — API + vector DB, API + LLM call, tool-calling paths
- [ ] **E2E tests** — full user flow (query → retrieval → reasoning → response) run as a black box pre-deployment
- [ ] **Mock the LLM/vector DB in unit and integration tests** — same rationale as mocking the ML model in the FastAPI playbook: real calls are slow, non-deterministic, and cost money on every test run
- [ ] Structured logging with proper levels (DEBUG/INFO/WARNING/ERROR/CRITICAL), not `print`
- [ ] Centralized exception handling so LLM/tool failures return consistent, clean responses instead of raw stack traces or a raw model error

### 15. Safety & Security
- [ ] Tool misuse prevention (ties to Layer A §7's allowlist)
- [ ] Sensitive data redaction — **Stack:** Microsoft Presidio for PII detection/redaction before data reaches the model or gets logged
- [ ] Output validation layer (schema-check every structured output before it's returned)
- [ ] Confidence threshold enforcement
- [ ] Refusal behavior defined
- [ ] Clarification strategy implemented for ambiguous input
- [ ] **[Added from your doc's later security section]** Prompt injection tests — **Stack:** promptfoo's redteam module or Garak, run on a schedule, not just once at launch
- [ ] Tool misuse simulations and RAG poisoning checks
- [ ] Input sanitization per modality (cross-reference Layer S §3)
- [ ] Guardrail failure detection — safeguards decay silently over time; test the guardrails themselves periodically, not just the happy path

### 16. Data Governance
- [ ] Retention duration defined per data type
- [ ] Embedding TTL / refresh policy — stale embeddings degrade retrieval quality silently
- [ ] User/tenant data isolated by namespace (critical if the vector DB or agent memory is shared infrastructure — see Layer X)
- [ ] Explicit rule for what is never used for training
- [ ] Deletion and reindex process documented and actually runnable, not theoretical

### 17. Cost & FinOps
- [ ] Max tokens per request enforced
- [ ] Cost per request/tool tracked — **Stack:** Langfuse/LangSmith both expose cost tracking natively per trace; Helicone is a lightweight proxy-based alternative if you want cost visibility without adopting a full observability platform
- [ ] Expensive paths gated by confidence (don't run the expensive tool/model unless the cheap path already indicates it's warranted)
- [ ] Budget alerts configured
- [ ] Cheap-model fallback available — **Stack:** this is exactly what LiteLLM's routing solves (fast/cheap model for simple queries, accurate/expensive model for hard ones)
- [ ] Cost caps tied to usage growth, so a viral spike doesn't turn into a surprise bill

### 18. Performance & Caching (engineering layer)
- [ ] Async execution used where the work is genuinely I/O-bound — **same correction as the FastAPI playbook: don't force `async def` around CPU-bound work**
- [ ] Embedding caching enabled — **Stack:** Redis, keyed on input hash
- [ ] Retrieval caching implemented — same Redis instance as the FastAPI playbook's Phase 7, extended to cache retrieval results, not just DB queries
- [ ] Response caching for identical/near-identical queries — **Stack:** GPTCache specifically does *semantic* caching (catches paraphrased duplicates, not just exact matches), which a plain Redis key-match won't
- [ ] Batch processing supported where the use case allows it (vectorized calls, same rationale as the FastAPI playbook's batch-prediction guidance)
- [ ] Load shedding strategy defined for traffic spikes
- [ ] Latency SLOs defined and benchmarked — **Stack:** Locust, same as the FastAPI playbook's Phase 8, tracking the same metrics (latency, throughput, concurrency, error rate, resource usage) plus LLM-specific ones (time-to-first-token, tokens/sec)

### 19. Observability & Ops (engineering layer)
- [ ] End-to-end tracing — **Stack:** LangSmith (if LangGraph-native) or Langfuse (framework-agnostic, self-hostable)
- [ ] Prompt + model version logged on every trace
- [ ] Failure taxonomy defined (retrieval failure / reasoning failure / tool failure / data-quality failure / user ambiguity) — retry rules per type, escalation path, and user-facing vs. internal error messages kept separate
- [ ] Infra metrics on top of LLM tracing — **Stack:** Prometheus + Grafana, exactly as in the FastAPI playbook's Phase 9, for request rate/latency/error rate at the API layer
- [ ] Incident response playbooks written
- [ ] On-call ownership defined
- [ ] **[Added]** A clear owner assigned for each subsystem (retrieval, agent/reasoning, tools, infra) — "everyone owns it" means no one debugs it at 2am
- [ ] **[Added]** A defined model/prompt release process — who approves a prompt or model change before it ships, separate from the code-review process
- [ ] **Drift monitoring:** scheduled re-evaluation runs, retrieval relevance tracked over time, prompt effectiveness monitored, model version compared over time — because LLM systems degrade *without throwing errors*, which is what makes drift dangerous

### 19a. Recovery from Partial Failure — **[Added, was missing entirely]**
- [ ] A partial-output strategy — if retrieval fails but the model can still answer generically, does it? Should it?
- [ ] Degraded-mode operation defined — which features can go offline individually without taking the whole system down
- [ ] Feature-level kill switches (ties to the feature-flag stack in the legend) so one broken tool/integration doesn't need a full rollback
- [ ] Clear, honest degraded-UX messaging — a system that fails "all or nothing" feels broken even when 80% of it still works

### 20. Human Trust & UX
- [ ] Confidence calibrated to actual accuracy (don't expose a confidence score that doesn't mean anything)
- [ ] Overconfidence detection
- [ ] Graceful uncertainty messaging — the system should be able to say "I'm not sure" convincingly
- [ ] Progressive disclosure — executive-summary mode vs. deep-dive mode, so the answer's complexity matches the user's need
- [ ] Behavioral feedback captured (follow-up question frequency, reformulation rate, abandonment) — users tell you the truth through behavior more than through ratings
- [ ] **[Added]** Answer length and information density explicitly bounded/adapted to user role — a technically correct answer that overwhelms the reader erodes trust just as much as a wrong one

### 20a. Human-in-the-Loop Workflow — **[Added, was missing]**
*(if the system has any human-review path at all)*
- [ ] Confidence threshold defined for routing an output to human review
- [ ] Feedback capture mechanism — how a human reviewer's correction gets recorded
- [ ] Correction loop defined — what happens to a correction after it's captured (ties to §22's knowledge-update approval flow, so corrections don't silently retrain the system unreviewed)
- [ ] A model-improvement pipeline exists, even if manual at first — reviewed corrections should visibly improve the system over time, not just sit in a log

### 21. Deployment & Operations (engineering layer)
- [ ] Environment separation (dev/staging/prod) — same as the FastAPI playbook's Phase 10
- [ ] Secrets managed securely per environment (see Stack Legend)
- [ ] Feature flags available for gradual rollout of new prompts/models
- [ ] Rollback strategy defined — for *both* code and prompt/model versions, since a prompt change is a deploy too
- [ ] Canary or A/B deployment supported for prompt and model changes specifically

### 22. Evolution & Aging
- [ ] Scheduled re-evaluations on a cadence, not "when something looks wrong"
- [ ] System entropy explicitly acknowledged — quality degrades even without code changes, as prompts drift, data decays, and users adapt to (and game) the system
- [ ] AI-specific tech-debt register: prompt debt, eval debt, "temporary" guardrails that never got removed
- [ ] Knowledge/feedback update approval flow — blind learning from user feedback is silent corruption risk, not improvement
- [ ] Exit/shutdown strategy — how the system turns off safely, how data gets extracted, how model dependencies get unwound

### 22a. Documentation & Maintenance — **[Added, was missing entirely]**
- [ ] System diagram exists and is kept current (not a one-time onboarding artifact)
- [ ] Decision rationale documented — *why* the architecture is what it is, not just what it is (this is what saves the next person from re-litigating a decision that was already made for a reason)
- [ ] Known failure cases listed somewhere discoverable, not just tribal knowledge
- [ ] Runbooks written for the common on-call scenarios
- [ ] Ownership defined (ties to §19's per-subsystem owner)
- [ ] A future-extension plan exists — what's the obvious next modality/tool/capability, and does the current architecture actually accommodate it

---

## Layer D — Development & Delivery
*"How do we build this without going broke or crazy?"*

### 23. Developer Experience
- [ ] Local mocking strategy for LLM/tool calls so tests cost $0 to run (VCR-style request replay, or the mocking approach from Layer E §14)
- [ ] Synthetic data pipeline for cold-start test cases
- [ ] Environment parity — prompts behave the same in dev/prod (seed control where the provider allows it)

### 24. User Perception Engineering
- [ ] Optimistic UI — a "thinking" state shows immediately, not a blank screen
- [ ] Intermediate steps streamed to the user for long agent runs ("Searching the document…", "Calling the pricing tool…") — this is both a UX and a trust-calibration technique
- [ ] Graceful degradation if the LLM is slow — a loader, not a frozen UI

**Stack:** Server-Sent Events (SSE) via FastAPI's `StreamingResponse` is the standard transport for one-way token/step streaming — simpler than WebSockets and sufficient for almost all LLM-response streaming. Reach for a full WebSocket connection only if the UI needs true bidirectional communication mid-generation (e.g., letting the user interrupt or redirect an in-progress agent run).

### 25. Multimodal Compliance
- [ ] Biometric scrubbing — faces/voices anonymized before analysis where required
- [ ] Consent granularity — users can revoke consent for specific modalities independently (e.g., keep text history, delete voice recordings)

---

## Layer X — Systemic Resilience (Senior-Level, Easy to Skip — Don't)
*The subtle failure modes that don't show up until the system has been live for months*

These were scattered across several "gap" rounds in your original doc. Consolidated here as one tight checklist rather than repeated across separate sections:

- [ ] **Semantic contract stability** — the JSON schema staying the same doesn't mean the *meaning* did; version behavior explicitly (e.g., v1 advisory-only → v2 actionable suggestions) so downstream systems don't silently misinterpret a stable-looking schema
- [ ] **Multi-user interference** — cross-session contamination checks, vector namespace leakage detection, agent memory strictly scoped per session/tenant (one user's data influencing another's answer is a severe incident, not a bug)
- [ ] **Answer irreversibility** — high-risk outputs (financial, medical, legal) get extra verification or a confirmation step before being treated as final
- [ ] **Emergence monitoring** — track for behaviors you didn't design: a tool becoming over-preferred, explanations drifting shorter/longer, clarifications stopping — via behavioral dashboards and pattern-frequency tracking over time
- [ ] **Meta-failure modes** — the guardrails themselves can fail silently; run red-team prompts and guardrail stress tests periodically, and audit for eval blind spots
- [ ] **Unknown-unknown detection** — not errors, just *weirdness*: distribution-shift monitoring on answer length, tool-call frequency, and response style, with a manual review queue for anomalies that don't trip a normal alert
- [ ] **System legibility** — a non-engineer needs to understand *why* an answer happened too; build a plain-English "why this happened" view and simplified incident reports, not just raw traces
- [ ] **Soft dependency management** — you don't control the model provider; canary-test against provider updates, and keep shadow runs on a frozen model version so a silent upstream change doesn't blindside you
- [ ] **Moral hazard awareness** — detect when users are outsourcing judgment entirely to the system, and nudge toward human verification rather than letting the system quietly become "the authority"
- [ ] **Success failure mode** — plan for things going *too well*: load-test the success path, cap costs against usage growth, because unexpected adoption breaks systems too
- [ ] **"Last human in the loop"** — periodic human audits and random sampling reviews that aren't metric-driven; metrics miss soul-level failures that only a human reading transcripts will catch
- [ ] **[Added] System humility mechanism** — explicit "I might be wrong because…" logic, and defined conditions where the system voluntarily steps back instead of answering confidently; trust increases when a system can admit its own limits
- [ ] **[Added] Cognitive load management** — bound answer length and information density to what the reader can actually absorb, not just what's technically complete; a correct answer nobody can process is a UX failure, not a win

---

## Final Self-Test — combined SANE-AI + engineering Definition of Done

Answer **yes** to all of these before calling the system production-grade:

**Design (SANE-AI):**
- [ ] Can I explain *why* the system answered this way?
- [ ] Can I swap the model in a day?
- [ ] Can I add a modality without rewriting logic?
- [ ] Can the system fail safely?
- [ ] Can humans override it easily?
- [ ] Can it age without becoming dangerous?

**Engineering (FastAPI playbook, applied to this system):**
- [ ] Folder structure separates capability layers cleanly (parsing / retrieval / reasoning / action / response — Layer A §6)
- [ ] All secrets in `.env`/vault, nothing hardcoded or committed
- [ ] Auth implemented and tested
- [ ] Unit + integration + E2E tests exist and pass; LLM and vector DB calls are mocked in tests
- [ ] Structured logging + centralized exception handling in place
- [ ] Caching applied to embeddings, retrieval, and repeated responses
- [ ] Profiled once, benchmarked once, cost-per-request known
- [ ] Tracing (LangSmith/Langfuse) *and* infra monitoring (Prometheus/Grafana) both wired up
- [ ] Dockerized and runnable via `docker-compose up --build`
- [ ] Deployed with environment separation, feature flags, and a rollback path for both code and prompts
- [ ] README is usable by someone who isn't you

If yes to all → SANE-AI-compliant *and* production-engineered.

---

## How to use this document alongside the FastAPI playbook

- **This document** is the design/architecture/risk spine for any GenAI or agentic project — read it first, at project kickoff, the same way you'd read the FastAPI playbook's Phase 1.
- **The FastAPI playbook** stays the reference for the pure serving/infra mechanics (exact folder layout, Docker/Prometheus/Grafana setup steps, curl-testing workflow) — this document points back to it rather than duplicating every command, so you have one source of truth for "how" and one for "what to design for."
- For a GenAI project specifically: start at Layer S here, use the FastAPI playbook's Phase 0 folder structure as your base and extend it with `app/agents/`, `app/rag/`, and `app/prompts/` directories to match Layer A's capability decomposition, then work through N → E → D → X in order.

*Source: your SANE-AI GenAI checklist (all four rounds, consolidated) + the FastAPI + ML Production Playbook, merged and cross-referenced. Tech stack recommendations current as of September 2026 — re-check the fast-moving categories (agent frameworks, observability tools) every few months, as this space moves quickly.*
