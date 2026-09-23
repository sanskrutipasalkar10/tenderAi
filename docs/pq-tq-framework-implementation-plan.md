# Implementation Plan — PQ/TQ/Bid-No-Bid Framework Integration

Target: Tender AI Platform backend (`backend/`). This plan integrates C4i4's actual
Bid/No-Bid decision framework (attached: `C4i4_Tender_PQ_TQ_BID_NO_BID_Framework.xlsx`)
and SUTF's statutory company profile (attached:
`sutf-company-profile-decision-grade.docx`) into the existing reduce pass, replacing a
freeform Go/No-Go judgment with a reproducible, auditable scoring formula.

**Read first:** `docs/SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
`docs/RUNBOOK.md`, and the backend study guide, all already in this repo — this plan
assumes and extends what's documented there, it doesn't restate it. Where this plan
conflicts with something in `docs/DECISIONS.md`, treat that file as authoritative and
flag the conflict rather than silently overriding a prior decision.

---

## 0. What's actually changing, in one paragraph

Today, `app/pipeline/reduce_pass.py`'s `run_go_no_go` asks the model to produce a score
and decision however it judges reasonable. This plan replaces that with: (a) a hard-gate
pre-check that can force NO-BID before any scoring happens, (b) an explicit weighted
formula over 8 named factors instead of a freeform number, and (c) a fixed 28-item PQ
checklist the extraction is checked against every time, instead of a freeform
`eligibility_summary`. Nothing about the pipeline shape (classify → extract → chunk →
map → reduce) changes — this is a reduce-pass and schema change, not an architecture
change.

---

## 1. New reference data (not company-specific — the taxonomy itself)

Add a migration (`migrations/0003_pq_tq_framework.py`, Alembic, following the pattern in
`0001_initial_schema.py`) creating:

```sql
CREATE TABLE pq_criteria (
    id            SERIAL PRIMARY KEY,
    sequence      INTEGER NOT NULL,        -- 1-28, matches the framework's own numbering
    criterion     TEXT NOT NULL,
    category      TEXT NOT NULL            -- 'legal' | 'financial' | 'experience' |
                                            -- 'personnel' | 'certification' | 'commercial'
);

CREATE TABLE tq_criteria (
    id            SERIAL PRIMARY KEY,
    criterion     TEXT NOT NULL,
    weight        NUMERIC NOT NULL         -- sums to 100 across all rows
);

CREATE TABLE bid_decision_factors (
    id            SERIAL PRIMARY KEY,
    factor        TEXT NOT NULL,
    weight        NUMERIC NOT NULL         -- sums to 100
);

CREATE TABLE hard_fail_gates (
    id            SERIAL PRIMARY KEY,
    gate          TEXT NOT NULL            -- verbatim from the framework's 7 gates
);
```

Seed these four tables from a new script `scripts/seed_pq_tq_framework.py` (same
upsert-by-exact-match pattern as `scripts/seed_company_profile.py`), populated verbatim
from the attached Excel's `PQ TQ Qualification` and `Quick BID Decision` sheets — the 28
PQ criteria, 12 TQ criteria with their weights, 8 Bid/No-Bid factors with their weights,
and the 7 hard-fail gates. Do not paraphrase the criterion text; a Maker/Checker
comparing this against the source spreadsheet later needs it to match exactly.

**Why a separate migration and seed script, not a JSON blob in code:** these criteria
are reference data that could reasonably change if C4i4 revises the framework — keeping
them queryable and seedable the same way `company_profiles` already is means a future
framework revision is a re-seed, not a code change.

---

## 2. Extend `company_profile` (or `company_profiles` — confirm exact existing table
name from `migrations/0001_initial_schema.py` before writing this migration)

Add columns, all nullable (most will be NULL until confirmed — see Section 7):

```sql
ALTER TABLE company_profiles ADD COLUMN
    cin TEXT,
    roc_number TEXT,
    section8_licence_number TEXT,
    date_of_incorporation DATE,
    pan TEXT,
    gstin TEXT,
    udyam_registration_number TEXT,
    msme_classification JSONB,          -- [{year, type}]
    ngo_darpan_id TEXT,
    authorised_capital_inr NUMERIC,
    paid_up_capital_inr NUMERIC,
    net_worth_inr NUMERIC,              -- NULL until a CA certificate is on file
    turnover_source TEXT,               -- 'udyam_filing' | other — see decision below
    directors JSONB,
    bank_details JSONB,
    employment_count JSONB,
    government_grants JSONB;
```

**`turnover_source` is the load-bearing field of this whole migration.** The existing
`annual_turnover` JSONB column stays, but every write to it must now also set
`turnover_source` to name which document the figure came from. This is the direct fix
for the exact problem found while compiling the SUTF profile — two turnover figures on
file with no record of which one was confirmed against which entity. Enforce this at
the application layer (reject a write to `annual_turnover` that doesn't also set
`turnover_source`), not just by convention.

Update `scripts/seed_company_profile.py` to accept these new fields from the JSON it
already reads (`scripts/seed_data/c4i4_lab_profile.json` — confirm exact filename per
`docs/DECISIONS.md #51`), and re-seed SUTF's record from the attached profile document's
Section 18 JSON payload, with `turnover_source: "udyam_filing"` and
`annual_turnover: {"2022_23": 26622460, "2023_24": 19039637}` — the Udyam-confirmed
figures, not the unconfirmed organizational-profile figures. Store the unconfirmed
larger figures in a clearly-named field if you want them retained at all — do not put
them in `annual_turnover` where they'd be silently used for scoring.

---

## 3. Hard-gate pre-check (new function, runs before scoring)

New function `check_hard_gates(document_analysis_facts, company_profile) -> list[str]`
in `app/pipeline/reduce_pass.py`, called at the start of `run_go_no_go` before any
scoring logic. Checks the 7 gates from `hard_fail_gates` against the extracted tender
facts and the company profile:

- Mandatory PQ experience unavailable
- Turnover not met and no valid exemption
- Mandatory certification unavailable
- Mandatory OEM authorization unavailable
- Mandatory manpower unavailable
- Required consortium/partner route unavailable
- Unacceptable legal/commercial terms

Returns a list of triggered gate names (empty list = no hard fail). **If the list is
non-empty, `decision` is forced to `"No-Go"` regardless of what the weighted score would
produce** — mirroring the spreadsheet's own instruction verbatim: "Any mandatory PQ
failure should trigger NO-BID unless a valid tender exemption/relaxation applies." The
triggered gates go into the existing `gaps[]` field so the citation-verification UI
surfaces *why*, not just *that* it failed.

This is a genuinely new control-flow branch, not a prompt change — write it as
deterministic code checking structured fields, not as an LLM judgment call, consistent
with `docs/SPEC.md §10`'s own rationale for why this system is a pipeline and not an
agent: deterministic steps stay as plain code.

---

## 4. Weighted scoring formula (replaces the freeform score)

Only runs if `check_hard_gates` returns empty. New function
`compute_weighted_score(criteria_matches, company_profile) -> tuple[float, dict]` in the
same file, implementing the exact 8-factor formula from the "Quick BID Decision" sheet:

| Factor | Weight |
|---|---|
| PQ Eligibility | 30 |
| Similar Experience | 20 |
| Technical Capability | 15 |
| Government / PSU Experience | 10 |
| Key Manpower | 10 |
| Financial Capability | 5 |
| Strategic Relevance | 5 |
| Partner / OEM Availability | 5 |

Each factor scores 0–100 individually (sub-scoring logic is the actual LLM judgment
call — the reduce-pass prompt should be updated to output these 8 sub-scores explicitly,
named exactly as above, rather than one holistic number), then the weighted sum is
computed in code, not by the model — this is what makes the final score reproducible
and checkable by a human against the same formula, not just trusted.

Apply the decision bands verbatim from the framework:

```python
def decide(score: float) -> str:
    if score >= 80: return "Go"
    if score >= 65: return "Go (Management Review)"
    if score >= 50: return "Conditional-Go (Partner Required)"
    return "No-Go"
```

Update the `go_no_go` result schema (`docs/SPEC.md §6`) to add a `factor_scores` object
alongside the existing `score`/`decision`/`criteria_matches`/`gaps`/`next_steps` —
additive, not a breaking change to the existing shape.

---

## 5. PQ checklist as explicit extraction target, not freeform text

Currently `synopsis`'s `eligibility_summary` is freeform text the model extracts however
it judges relevant, per the backend guide's description of `run_synopsis`. Change the
map-pass prompt (`app/prompts/`, versioned per the existing convention) to check the
tender against the 28 named PQ criteria explicitly — for each criterion in
`pq_criteria`, extract whether the tender states a requirement for it and what that
requirement is, tagged with `page_ref` as every other extracted fact already is.

This closes a real coverage gap: today, whether a tender's specific manpower minimum or
consortium eligibility rule gets surfaced depends on whether the freeform summary
happened to mention it. Against a fixed 28-item checklist, every tender gets checked for
all 28, every time, and a criterion the tender simply doesn't mention is recorded as
such rather than silently absent.

Store this as a new `pq_requirements` JSONB array on the `go_no_go` module's result
(one entry per criterion: `{criterion_id, tender_requirement, company_position,
status, page_ref}`) — `company_position` is populated by joining against the
`company_profile` fields this plan adds in Section 2, exactly matching the crosswalk
already built in the attached profile document's Section 16.

---

## 6. Maker/Checker = the existing citation-verification UI (no new workflow)

**Do not build a new approval workflow.** `docs/SPEC.md §12`'s HITL note already
establishes that this system's human-in-the-loop mechanism is the citation-verification
UI — every claim carries a `page_ref` a human clicks to verify — and explicitly states
there is no separate approve/override workflow in scope. The framework's Maker/Checker
pattern maps onto this directly:

- **Maker's first pass** = the AI's `go_no_go` output (score, decision, `pq_requirements`
  with citations) — this is what already happens today.
- **Checker step** = the existing citation-verification UI, used by a second person to
  independently confirm each `page_ref` before acting on the decision.

The only change needed here is documentation, not code: add a short note to
`docs/RUNBOOK.md`'s on-call/ownership section making this mapping explicit, so a future
reader doesn't think Maker/Checker is an unbuilt feature. Do not add sign-off fields,
approval states, or a second workflow — that would contradict the Tier-2 scope decision
already recorded in `docs/DECISIONS.md` row 3.

---

## 7. New fields that are workflow metadata, not extracted facts

Add to `documents` (or a small companion table if preferred — confirm against the
existing schema before choosing):

```sql
ALTER TABLE documents ADD COLUMN
    bid_manager TEXT,
    tender_portal TEXT,
    date_of_assessment DATE;
```

These come from `routes_ingest.py`'s upload form (human-entered), not from the PDF or
any AI extraction — do not route these through the pipeline, classification, or any LLM
call. They exist purely so the Excel export (Section 8) has somewhere to pull them from.

---

## 8. Excel export in the framework's exact layout

New endpoint, `GET /documents/{id}/export/pq-tq` (alongside whatever export endpoints
already exist per `docs/SPEC.md`/the backend guide), generating an `.xlsx` matching the
attached framework's exact sheet structure and column order — same section headers (A.
PRE-QUALIFICATION, B. TECHNICAL QUALIFICATION, C. BID/NO-BID DECISION, etc.), pre-filled
from:

- Section A rows ← `pq_requirements` (Section 5 above)
- Section B rows ← `factor_scores`/TQ sub-scores (Section 4)
- Section C ← `decision`, hard-gate results, `score`
- Header fields (Tender/Bid No., Buyer, Bid Manager, Date of Assessment) ← `documents`
  table fields from Section 7

Leave the Maker/Checker sign-off checkboxes and signature fields blank in the export —
those are filled by a human after the Checker step (Section 6), not by the system.

**Why match the layout exactly rather than design a new one:** the goal is a bid team
that already trusts this spreadsheet gets the AI's answer inside a format they don't
have to relearn — a redesigned layout would undermine exactly the adoption this feature
is for.

---

## 9. Eval/testing additions (`evals/`, following the existing golden-fixture pattern)

- `test_hard_gates.py` — fixture tenders/profiles engineered to trip each of the 7
  gates individually; assert `decision == "No-Go"` regardless of what the weighted score
  would otherwise be, and that the triggered gate appears in `gaps[]`.
- `test_weighted_score_reproducibility.py` — given fixed `factor_scores`, assert
  `compute_weighted_score` returns the exact expected weighted sum and band — this is
  pure arithmetic, not an LLM eval, so it should be a fast deterministic unit test, not
  a golden-dataset LLM eval.
- `test_pq_coverage.py` — assert every one of the 28 `pq_criteria` rows produces an
  entry in `pq_requirements` for a real fixture tender (even if `status: "not stated"`)
  — this is the regression test for the coverage gap described in Section 5.
- Update `scripts/report_cost.py` if the map-pass prompt change materially changes
  token volume per chunk (it likely will, given 28 explicit criteria to check per
  chunk) — re-baseline the cost report, don't assume it's unchanged.

---

## 10. Suggested sequencing

1. Migrations (Sections 1, 2, 7) — schema first, no behavior change yet.
2. Seed scripts (`seed_pq_tq_framework.py`, updated `seed_company_profile.py` with SUTF's
   corrected data) — populate before anything reads them.
3. Hard-gate check (Section 3) — deterministic code, testable in isolation before
   touching the LLM prompts.
4. Weighted scoring (Section 4) — prompt + formula change together, since the formula
   depends on the prompt naming the 8 factors correctly.
5. PQ checklist extraction (Section 5) — the map-pass prompt change; expect this to be
   the highest-risk step for prompt-engineering iteration, budget accordingly.
6. Excel export (Section 8) — depends on everything above existing first.
7. Evals (Section 9) — write alongside each step above, not batched at the end; the
   hard-gate and reproducibility tests in particular should exist before Section 4 is
   considered done, not after.
8. Docs (Section 6) — the RUNBOOK note, quick to do, don't let it slip to "later."

## 11. Explicit non-goals for this change

- No new approval/sign-off workflow (Section 6) — stays Tier-2 scope as already decided.
- No change to the pipeline shape (classify → extract → chunk → map → reduce → serve) —
  this is confined to the reduce pass, the schema, and one new prompt's scope.
- No attempt to resolve the SUTF vs. Indi4 turnover/registration ambiguity in code — the
  `turnover_source` field (Section 2) makes the ambiguity queryable and auditable, it
  doesn't resolve it. That resolution needs a human with knowledge of the actual
  corporate structure, not a schema change.
- Do not delete or silently drop the unconfirmed organizational turnover figures — retain
  them under a clearly separate field name per Section 2, consistent with this whole
  project's "never lose a source figure, flag it instead" principle.
