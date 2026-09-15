# Decision Log — Tender AI Platform

Add a row every time a technical choice is made. This is the difference between "I built
a tender-analysis pipeline" and "I chose X over Y because Z, measured how."

| # | Decision | Options considered | Chose | Why | Revisit if |
|---|---|---|---|---|---|
| 1 | Backend language | Python/FastAPI, Node/Fastify | Python/FastAPI | Confirmed with user; PyMuPDF/pdfplumber/Camelot are Python-native, keeps pipeline one language | Never without explicit new ask |
| 2 | Project tier | 1 / 2 / 3 | Tier 2 — Internal/Pilot | Internal bid-team users only; blast radius is "bad internal decision," not customer-facing | Pilot expands externally or multi-org |
| 3 | HITL mechanism | Full approve/override + correction table vs. citation-verification UI | Citation-verification UI | Every output already carries `page_ref` per spec's own success criteria; satisfies Tier 2's "if high-stakes" HITL requirement without new schema | Users start needing systematic correction feedback into prompts/evals |
| 4 | Architecture shape | Pipeline / single agent+tools / multi-agent | Pipeline (Celery map-reduce) | All stages deterministic and fixed; no runtime branching decision exists; not RAG, no retrieval loop to wrap in an agent | A future feature needs dynamic tool selection |
| 5 | LLM provider access | Direct SDK calls per stage vs. LiteLLM wrapper | LiteLLM via `app/llm/client.py` | Keeps "swap model in a day" true; centralizes retry/backoff/timeout once instead of 3x | Never — low-cost even at small provider count |
| 6 | Job orchestration | Celery+Redis / RQ+arq / FastAPI BackgroundTasks | Celery + Redis | Spec requires async per-chunk retries, not one long sync request; chord/group maps directly onto map(fan-out)→reduce(fan-in) | Pipeline complexity shrinks enough a simpler queue suffices |
| 7 | Auth | JWT / OAuth-Clerk / NextAuth | JWT via FastAPI `security.py` | Tier 2 requires JWT/OAuth; no social-login need stated; internal users provisioned directly | Pilot needs SSO with company IdP |
| 8 | Tracing tool | LangSmith / Langfuse | Langfuse | LangSmith's edge is native LangChain/LangGraph integration; this project uses neither | Project later adopts LangGraph for a genuinely agentic feature |
| 9 | Eval harness | Ragas / custom pytest+golden JSONL | Custom pytest (DeepEval-style) over `evals/datasets/*.jsonl` | Ragas metrics are retrieval-specific; no retrieval step exists here | A future retrieval feature (chat-over-tender) ships |
| 10 | `pgvector` extension | Enable now unused / enable later | Enable now, no vector columns in MVP | Per spec §2.7 — avoids disruptive migration later, zero cost now | Never — already decided in source spec |
| 11 | Object storage | MinIO local / direct cloud S3 in dev too | MinIO local → S3/R2 prod | Per spec §2.2/2.6 — S3-compatible API, zero code change on migration | Prod target changes away from S3-compatible storage |
| 12 | Vision extraction provider | Gemini-only / Ollama-only / Gemini primary+Ollama fallback | Gemini free tier primary, `qwen2.5vl:7b` via Ollama (`USE_LOCAL_VISION=true`) | Gemini also does reduce pass (needs vision anyway), free-tier no card; Ollama covers offline/quota-exhaustion | Gemini free tier discontinued, or pilot needs air-gapped operation |
| 13 | Migration tool | Alembic vs. hand-run DDL | Alembic, DDL from spec §3.1 applied verbatim in the first migration | Spec explicitly calls for a migration tool from day one, not hand-run DDL against a long-lived DB | Never |
