# Tender AI Platform — Spec

## 1. Responsibility
This system reads uploaded Indian government tender PDFs (50–1000+ pages, mixed native
text / scanned images / tables) and produces three outputs per tender for a bid team:
a Go/No-Go recommendation scored against the company's profile, a structured synopsis,
and a page-cited risk list.
It does NOT auto-fetch tenders from GeM/CPPP/state portals, does NOT estimate BOQ costs
or auto-fill tender forms, does NOT support chat/Q&A over a tender, and does NOT decide
or submit a bid on the company's behalf.

## 2. Tier
Tier: 2 — Internal / Pilot
Deliberately skipped (documented here and in DECISIONS.md):
- Full RBAC (JWT auth only; single internal bid-team user class)
- Budget alerts / FinOps automation beyond token/page caps
- Automated drift monitoring (quarterly manual re-eval instead)
- Layer X systemic resilience — apply only: soft-dependency/provider canary awareness,
  semantic contract stability on `document_analysis.result`, "last human in the loop" spot checks
- Exit strategy — shallow (data export path in RUNBOOK.md, not a full unwind plan)
- Separate HITL correction-capture/override workflow — see HITL note below

## 3. Behavior mode
[x] Advisory — surfaces information, human decides
[ ] Autonomous
Irreversible outputs: none. The system never submits, emails, or files anything externally;
every output (score, synopsis, risk list) is read-only until a human acts on it.

## 4. Users & domain
Primary user: a bid-team member at a construction/services company, domain-expert in
tenders but not in AI — evaluates the system's output before deciding whether to bid.

In-domain questions (3 examples):
- "Upload this NHAI road-construction tender and tell me if we should bid."
- "What's the liquidated damages clause and how risky is it?"
- "Does our ISO certification meet the eligibility criteria?"

Out-of-domain questions it must refuse (3 examples):
- A non-tender PDF (e.g. an annual report or a random contract) — flagged as "does not
  appear to be a tender document" rather than silently analyzed.
- A tender in a modality the pipeline can't classify (e.g. entirely handwritten, no
  OCR-legible content) — low confidence surfaced, not a confident wrong answer.
- "Should we increase our bid margin on this?" (pricing/commercial strategy) — out of
  scope for MVP (no BOQ/cost-estimation module); redirect to the synopsis/risk output only.

Out-of-domain behavior: refuse/flag with a visible reason, never silently proceed.

## 5. Inputs
| Modality | Source | Volume | Limits | Validation |
|---|---|---|---|---|
| PDF (tender document) | User upload via web UI | 50–1000+ pages/doc; pilot volume: low tens of docs/week | Proposed ceiling: 2000 pages / 500MB per file (OPEN — confirm before Phase 6) | PyMuPDF open-and-validate at ingestion: reject non-PDF MIME, reject 0-page/corrupt PDF, reject over ceiling, log rejected uploads |
| company_profile (JSON) | User input via web UI, created once per company, reused across tenders | 1 profile per pilot company | Required-field subset TBD (OPEN) | Pydantic schema validated against the `company_profiles` JSONB shape before the reduce pass will run |

## 6. Outputs
Format: JSON (three `document_analysis.result` shapes, one row per `(document_id, module)`)

Schema (`go_no_go`):
```jsonc
{
  "score": 78,
  "decision": "Go",
  "criteria_matches": [
    { "criterion": "Minimum turnover", "required": "50 Cr", "company_value": "72 Cr", "status": "pass" }
  ],
  "gaps": [],
  "next_steps": ["Prepare EMD of INR 91.2 lakh", "Submit ISO 9001 certificate"]
}
```

Schema (`risk_finder`):
```jsonc
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

Schema (`synopsis`):
```jsonc
{
  "title": "...", "issuing_authority": "...",
  "key_dates": [{"label": "Bid submission deadline", "value": "2026-11-03", "page_ref": 4}],
  "financials": [{"label": "EMD", "value": "INR 91.2 lakh", "page_ref": 7}],
  "scope_summary": "...", "eligibility_summary": "...", "payment_terms_summary": "...",
  "confidence": "high"
}
```

Must include: [x] confidence  [x] citations  [x] "I don't know" path
- Confidence: page-level `confidence_score` + module-level rollup.
- Citations: `page_ref` on every extracted fact/risk/criterion.
- "I don't know" path: `Conditional-Go` + `gaps[]` when `company_profile` is incomplete;
  a low-confidence fact/risk is shown as unverified, never hidden or guessed.

## 7. Hallucination tolerance
Level: **zero** for financial figures, dates, and any extracted fact used as a
`criteria_match` input (turnover figures, certification names, EMD amounts, deadlines) —
these must trace to literal page text, never inferred or rounded by the model.

Level: **low** for risk severity categorization and the Go/No-Go judgment itself —
inherent interpretive judgment is expected here, but every risk must still be grounded in
a real clause on a real page; the model must never invent a risk category that has no
corresponding page span.

Rationale: a hallucinated EMD amount or deadline is a business-critical, potentially
costly error (missed deadline, wrong bid guarantee); a defensible-but-imperfect severity
call is recoverable because the underlying clause is always shown for the human to re-judge.

What happens when the system isn't sure: page-level `confidence_score` below threshold →
excluded from Reduce-pass facts, or included but marked `verified: false`; missing
`company_profile` fields → `decision: "Conditional-Go"` with the missing fields listed in
`gaps[]`, not a guessed Go/No-Go.

## 8. Success criteria
| Metric | Target | How measured |
|---|---|---|
| All three module outputs returned for a real mixed-format tender, every risk flag citing a real page | 100% of `risk_finder.risks[].page_ref` resolve to an existing `pages` row for that `document_id` | `evals/test_citation_verifiability.py` + manual spot check on one real pilot tender |
| Boilerplate reuse across near-duplicate tenders from the same issuing authority | `boilerplate_cache.hit_count` increments > 0 on the second of two near-duplicate fixture uploads | Phase 3 fixture test |
| Re-opening an already-analyzed tender | Zero pipeline recomputation; result served directly from `document_analysis` | `document_analysis` `UNIQUE(document_id, module)` upsert check + timing assertion |
| Zero silently dropped pages | `COUNT(pages) == documents.total_pages` for every document with `status='extracted'` or later | Hard invariant test, runs on every processed document from Phase 2 onward |
| Page classification accuracy | ≥95% agreement with hand-labeled golden set (PROPOSED — tune via Phase 1) | `evals/test_classification.py` |
| Vision extraction accuracy on scanned/table pages | ≥90% field-level correctness on golden scanned/table sample (PROPOSED) | `evals/test_extraction_completeness.py` |
| p95 latency, full pipeline, 500-page tender | <15 min (PROPOSED — completeness over speed per spec's own stated priority) | Timing harness in Phase 7 |
| Cost/document | <$0 required spend (free-tier models only) | Token/page accounting per document in Phase 7 |

Note: the numeric targets above are proposed by this plan to make the spec's qualitative
success criteria CI/eval-gateable per Tier 2's requirement, and are flagged as tunable.

## 9. Scale & budget
Expected volume: pilot — low tens of tenders/week, single internal bid team.
Peak concurrency: low (few simultaneous uploads); Celery worker concurrency tuned for
per-chunk parallelism within one document, not many concurrent documents.
Monthly cost ceiling: $0 required (free-tier Gemini + Groq + optional local Ollama);
paid tier only as an opt-in fallback if free-tier quotas are hit, never silently.
Latency SLO: see p95 target above — advisory only, no real-time constraint.

## 10. Architecture decision
[x] Pipeline (no agent)  [ ] Single agent + tools  [ ] Multi-agent

Rationale — why NOT an agent:
Every stage (classify → extract → dedupe-check → chunk → map → reduce → serve) is fixed
at design time; nothing in the pipeline requires an LLM to choose which tool to call
next, whether to retrieve again, or how many steps to take. Classification is rule-based
code, not an LLM call. The map pass runs the same fixed prompt over every chunk; the
reduce pass runs one of three fixed prompts per module. Per the GenAI Playbook's Layer A
§5: "Agent used only where actual decisions/branching are required — deterministic steps
(parsing, formatting, DB writes) stay as plain code." Celery's per-chunk retries are
infrastructure resilience (retry-on-failure), not agentic reasoning/branching in the
SANE-AI sense. This is also explicitly not a RAG system (no retrieval step to wrap in a
ReAct-style loop), which removes the other common reason projects reach for an agent framework.

## 11. Key assumptions (and what breaks if wrong)
| Assumption | If false, then... | Runtime check? |
|---|---|---|
| Uploaded PDF is a genuine tender document | Pipeline wastes compute / produces nonsense outputs on an out-of-domain file | Phase 6 guardrail: lightweight "is this a tender" heuristic before full pipeline runs; adversarial eval case |
| Rule-based page classifier correctly separates native/scanned/table | Wrong extraction path used → garbled or missing text | Phase 2 gate: classification accuracy vs golden set; `confidence_score` stored per page |
| Vision model transcribes scanned/table pages faithfully | Silent fact errors downstream (wrong dates/amounts) | `confidence_score` threshold + citation re-verification at display time; Phase 3 golden eval |
| `company_profile` is complete enough to score against | Go/No-Go score is meaningless or misleading | Required-fields check before reduce pass; Conditional-Go / `gaps[]` path fires and is shown, not guessed |
| Map-pass chunk facts are all correctly page-tagged | Reduce pass cites the wrong page, breaking the core verifiability promise | Phase 4 gate: page-tag correctness on golden `chunk_extractions`; Phase 5 re-verifies `page_ref` against raw `pages` before display |
| SHA-256 content-hash matching catches true boilerplate duplicates without false positives | Missed cache hits (wasted cost) or a near-duplicate-but-different page served cached content | Exact-hash-match only (no fuzzy match) — false positives structurally prevented; near-duplicate-but-not-identical text won't cache-hit (documented limitation); Phase 3 fixture test |
| Free-tier provider rate limits are sufficient for pilot volume | Pipeline stalls/fails under real load | Retry/backoff on every provider call (CLAUDE.md rule 10); Phase 7 per-document cost/latency tracking |

## 12. Explicitly out of scope (v1)
- Auto-fetching tenders from GeM/CPPP/state portals (manual upload only)
- Multi-tenant / multi-organization support
- BOQ cost estimation or auto-filling tender forms
- Chat/Q&A interface over a tender (no retrieval, no `chunk_embeddings` table — `pgvector`
  extension enabled but unused, per spec §2.7)
- Full RBAC (JWT auth only)
- Automated drift monitoring (quarterly manual re-eval)
- Budget alerts / FinOps automation beyond simple token/page caps
- A separate HITL correction-capture/override workflow — see note below
- Semantic response caching (GPTCache-style) — the `document_analysis` `UNIQUE`
  constraint already gives upsert-not-recompute semantics; a second caching layer is not
  needed for MVP

### HITL note (explicit, not an oversight)
Tier 2 requires HITL "if high-stakes output." This system's HITL mechanism is the
**citation-verification UI**: every risk flag, synopsis fact, and Go/No-Go criterion
carries a `page_ref` the user clicks to view the original page image/text side-by-side
with the claim — this is the spec's own success criterion ("every AI claim must cite a
page number and be verifiable"). There is no separate approve/override workflow and no
correction-capture table in MVP; a human reviews by verifying citations, not by
submitting structured corrections that retrain the system. This is a deliberate Tier-2
scope choice, repeated in DECISIONS.md row 3.
