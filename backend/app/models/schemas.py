"""Pydantic schemas for API request/response bodies and internal pipeline data.

Kept separate from the SQLAlchemy ORM models in this package (never return ORM objects
directly from routes — FastAPI playbook Phase 3) and from the LLM-facing schemas in
app/prompts (which validate model output, not internal pipeline handoffs).
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PageClassification = Literal["native_text", "scanned_image", "table", "mixed"]
ExtractionMethod = Literal["native", "vision_cloud", "vision_local"]
DocumentStatus = Literal[
    "uploaded", "classifying", "extracting", "extracted", "analyzing", "ready", "failed"
]


# --- Internal pipeline results (classify.py / extract_native.py / extract_vision.py) --


class PageExtractionResult(BaseModel):
    """What every extraction path (native or vision) must produce for one page.

    A page ALWAYS produces one of these, even on failure (low confidence, empty
    raw_text) — CLAUDE.md's zero-page-drop invariant depends on this never being
    silently skipped upstream.
    """

    page_number: int = Field(ge=0)
    classification: PageClassification
    extraction_method: ExtractionMethod | None = None
    raw_text: str | None = None
    content_hash: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)


class TableCellData(BaseModel):
    headers: list[str]
    rows: list[list[str]]


# --- Map-pass output (app/pipeline/map_pass.py) — validates the model's JSON response
# before it's trusted, per CLAUDE.md hard rule 4. Shape matches the DDL's own comment
# on chunk_extractions.structured_json: "{dates:[], amounts:[], criteria:[],
# risk_candidates:[...]}, each item cites a page" (spec §3.1). --------------------


class MapPassDateFact(BaseModel):
    label: str
    value: str
    page_ref: int = Field(ge=0)


class MapPassAmountFact(BaseModel):
    label: str
    value: str
    page_ref: int = Field(ge=0)


class MapPassCriterionFact(BaseModel):
    description: str
    page_ref: int = Field(ge=0)


class MapPassRiskCandidate(BaseModel):
    category: str
    clause_summary: str
    page_ref: int = Field(ge=0)


class MapPassDocumentRequirement(BaseModel):
    """A specific document/form/certificate copy the tender asks the bidder to
    physically submit as part of the bid package — a literal packing-list item, not an
    eligibility judgment. Can legitimately overlap with `criteria` (e.g. both a
    turnover threshold and "submit audited balance sheet" may appear for the same
    underlying requirement) — that's expected, not a data-quality issue.
    """

    description: str
    page_ref: int = Field(ge=0)


class MapPassResult(BaseModel):
    dates: list[MapPassDateFact] = Field(default_factory=list)
    amounts: list[MapPassAmountFact] = Field(default_factory=list)
    criteria: list[MapPassCriterionFact] = Field(default_factory=list)
    risk_candidates: list[MapPassRiskCandidate] = Field(default_factory=list)
    documents_required: list[MapPassDocumentRequirement] = Field(default_factory=list)


# --- Reduce-pass output (app/pipeline/reduce_pass.py) — validates each module's model
# response before it's trusted (hard rule 4). Severity (risk_finder) and decision/score
# (go_no_go) are deliberately NOT part of what the model returns — CLAUDE.md hard rule 3
# ("score-formula math are code, not prompt instructions") and the plan's own open
# decision ("risk severity thresholds... encode as an explicit rubric, not model
# discretion") — reduce_pass.py computes both in code from the model's more narrowly
# interpretive output (which criteria pass/fail, which clause is which risk category). --


# "insufficient_data" (added following up on docs/DECISIONS.md #64): distinguishes a
# criterion with no relevant company_value at all from a criterion with a clear,
# evidenced mismatch. Both behave like a fail for gate-triggering purposes until a
# human resolves it (see GoNoGoHumanOverride) — never a free pass by default — but are
# never visually indistinguishable, unlike before.
GoNoGoStatus = Literal["pass", "fail", "insufficient_data"]
GoNoGoCriterionType = Literal["eligibility", "procedural"]
# Score bands per docs/pq-tq-framework-implementation-plan.md §4 / the SUTF docx's
# Table 26 (Phase 1 — see docs/DECISIONS.md): replaces the old 3-value
# freeform decision with the framework's own graded bands. "Go"/"No-Go" are
# unchanged strings, so existing evals/datasets/golden_go_no_go.jsonl fixtures
# (which only ever expect "Go" or "No-Go") stay valid.
GoNoGoDecision = Literal[
    "Go", "Go (Management Review)", "Conditional-Go (Partner Required)", "No-Go"
]
RiskSeverity = Literal["HIGH", "MEDIUM", "LOW"]
SynopsisConfidence = Literal["high", "medium", "low"]


class GoNoGoHumanOverride(BaseModel):
    """A bid-team member's resolution of a criterion the model couldn't confidently
    score — set via PATCH .../analysis/go_no_go/review, never by the model itself.
    No per-reviewer identity: this system has a single shared credential, not a
    per-user table (docs/DECISIONS.md #44) — `note` + `reviewed_at` is the full audit
    surface by design, not an oversight.
    """

    status: Literal["pass", "fail"]
    note: str | None = None
    original_status: GoNoGoStatus
    reviewed_at: datetime


class GoNoGoCriterionMatch(BaseModel):
    criterion: str
    required: str
    company_value: str
    status: GoNoGoStatus
    page_ref: int = Field(ge=0)
    # One of app.pipeline.reduce_pass.HARD_FAIL_GATES if this criterion's failure
    # triggers a hard gate, else None. Only ever meaningful when status == "fail".
    # Never set on a "procedural" criterion — enforced in code (check_hard_gates), not
    # only by prompt instruction, per CLAUDE.md hard rule 3.
    gate: str | None = None
    # "eligibility" (a real company-capability fact — turnover, certifications,
    # experience) vs. "procedural" (a bid-package mechanic — signatures, translations,
    # formats — satisfiable by any competent bidder, not a company attribute). Only
    # eligibility criteria feed check_hard_gates / are reviewable via human override.
    criterion_type: GoNoGoCriterionType = "eligibility"
    human_override: GoNoGoHumanOverride | None = None


class GoNoGoLLMResult(BaseModel):
    """What the model returns for go_no_go — criteria comparison plus the 8 named
    factor sub-scores (app.pipeline.reduce_pass.BID_DECISION_FACTOR_WEIGHTS).
    `decision`, `score`, and `gaps` are computed by reduce_pass.py from this, never
    asked of the model directly (CLAUDE.md hard rule 3).
    """

    criteria_matches: list[GoNoGoCriterionMatch] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    factor_scores: dict[str, int] = Field(default_factory=dict)


class GoNoGoRescoreLLMResult(BaseModel):
    """What the model returns for the "Resubmit analysis" rescoring call
    (app.pipeline.reduce_pass.rescore_go_no_go) — triggered once a bid-team member has
    finished reviewing insufficient_data/fail criteria, so the 8 factor_scores can be
    re-asked grounded in the now-authoritative, human-reviewed statuses. This call
    never re-derives criteria_matches itself (those are fixed input, not re-asked) —
    only factor_scores. score/decision/gaps are still computed in code from this
    (CLAUDE.md hard rule 3), exactly as in the main go_no_go call.
    """

    factor_scores: dict[str, int] = Field(default_factory=dict)


# "not_applicable" (distinct from GoNoGoStatus) — the fixed 28-item PQ checklist
# (app.pipeline.reduce_pass.PQ_CHECKLIST_CATEGORIES) always has one row per category,
# and most tenders won't state a requirement for every one of the 28 — that's a real,
# common, different case from "unknown"/"fails," not an omission.
PQChecklistStatus = Literal["pass", "fail", "insufficient_data", "not_applicable"]


class PQChecklistItem(BaseModel):
    category: str  # one of app.pipeline.reduce_pass.PQ_CHECKLIST_CATEGORIES
    tender_requirement: str | None = None
    company_value: str | None = None
    status: PQChecklistStatus
    page_ref: int | None = None


class PQChecklistLLMResult(BaseModel):
    """What the model returns for the separate PQ-checklist call
    (app.pipeline.reduce_pass._run_pq_checklist) — informational only, never feeds
    check_hard_gates/compute_weighted_score/decide (docs/DECISIONS.md).
    """

    items: list[PQChecklistItem] = Field(default_factory=list)


# Used for both commercial_competitiveness and bid_preparation_effort — same 3-level
# judgment shape, distinct meaning per field.
TQCompetitivenessLevel = Literal["LOW", "MEDIUM", "HIGH"]


class TQScoringLLMResult(BaseModel):
    """What the model returns for the separate Section-B TQ-scoring call
    (app.pipeline.reduce_pass._run_tq_scoring). Bundles the 12 TQ factor scores with
    Section C's two genuinely-judgment-based fields (commercial_competitiveness,
    bid_preparation_effort) and two free-text gap summaries — a 4th separate call per
    document wasn't justified for just those two fields (docs/DECISIONS.md).
    `tq_score` itself is computed in code from `factor_scores`
    (app.pipeline.reduce_pass.compute_tq_score), never asked of the model directly
    (hard rule 3).
    """

    factor_scores: dict[str, int] = Field(default_factory=dict)
    commercial_competitiveness: TQCompetitivenessLevel
    bid_preparation_effort: TQCompetitivenessLevel
    major_qualification_gap: str
    major_technical_gap: str


class GoNoGoResult(BaseModel):
    """The full go_no_go document_analysis.result shape (docs/SPEC.md §6)."""

    score: int = Field(ge=0, le=100)
    decision: GoNoGoDecision
    criteria_matches: list[GoNoGoCriterionMatch] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    # The 8 weighted factor sub-scores behind `score` (additive field — Phase 1,
    # docs/DECISIONS.md). None only for the pre-LLM short-circuit paths (missing
    # profile fields / no criteria found).
    factor_scores: dict[str, int] | None = None
    # The fixed 28-item PQ checklist (docs/DECISIONS.md) — additive, informational
    # only. None on the short-circuit paths above, or if the separate LLM call that
    # produces it failed (degrades gracefully, never blocks the main decision).
    pq_checklist: list[PQChecklistItem] | None = None
    # The literal document/attachment submission checklist (docs/DECISIONS.md) —
    # unlike pq_checklist, this needs no LLM call at all here (already extracted
    # per-chunk by map_pass) and no company profile, so it's always populated —
    # including on the short-circuit paths above, since "what to attach" doesn't
    # depend on whether we could determine eligibility.
    documents_required: list[MapPassDocumentRequirement] = Field(default_factory=list)
    # Section B (12-item Technical Qualification score, docs/DECISIONS.md) — same
    # additive/None-on-short-circuit-or-call-failure pattern as pq_checklist above.
    # tq_score is compute_tq_score(tq_factor_scores), never asked of the model.
    tq_score: int | None = None
    tq_factor_scores: dict[str, int] | None = None
    # Section C's two genuinely-judgment-based fields — the rest of Section C (PQ
    # Gate, Expected TQ Score, Strategic Relevance, Partner Required, Final
    # Recommendation) is assembled in the frontend from fields already above, not
    # stored separately (docs/DECISIONS.md).
    commercial_competitiveness: TQCompetitivenessLevel | None = None
    bid_preparation_effort: TQCompetitivenessLevel | None = None
    major_qualification_gap: str | None = None
    major_technical_gap: str | None = None


class GoNoGoCriterionOverride(BaseModel):
    """One human review decision, submitted via PATCH .../analysis/go_no_go/review."""

    criterion_index: int = Field(ge=0)
    status: Literal["pass", "fail"]
    note: str | None = None


class GoNoGoReviewRequest(BaseModel):
    overrides: list[GoNoGoCriterionOverride] = Field(min_length=1)


class RiskFinderLLMRisk(BaseModel):
    """What the model returns per risk — category/clause/page only. `severity` is
    assigned by reduce_pass.py's code-based rubric, `verified` by citation_verify.py.
    """

    category: str
    clause_summary: str
    page_ref: int = Field(ge=0)


class RiskFinderLLMResult(BaseModel):
    risks: list[RiskFinderLLMRisk] = Field(default_factory=list)


class RiskFinderRisk(BaseModel):
    category: str
    clause_summary: str
    severity: RiskSeverity
    page_ref: int = Field(ge=0)
    verified: bool = False


class RiskFinderResult(BaseModel):
    """The full risk_finder document_analysis.result shape (docs/SPEC.md §6)."""

    risk_score: int = Field(ge=0, le=100)
    risks: list[RiskFinderRisk] = Field(default_factory=list)


class SynopsisLLMResult(BaseModel):
    """What the model returns for synopsis — prose fields only. `key_dates` and
    `financials` are populated by reduce_pass.py directly from the already-verified,
    page-cited map-pass facts (hard rule 7: zero hallucination tolerance for dates/
    amounts) rather than asked of the model a second time.
    """

    title: str
    issuing_authority: str
    scope_summary: str
    eligibility_summary: str
    payment_terms_summary: str
    confidence: SynopsisConfidence


class SynopsisResult(BaseModel):
    """The full synopsis document_analysis.result shape (docs/SPEC.md §6)."""

    title: str
    issuing_authority: str
    key_dates: list[MapPassDateFact] = Field(default_factory=list)
    financials: list[MapPassAmountFact] = Field(default_factory=list)
    scope_summary: str
    eligibility_summary: str
    payment_terms_summary: str
    confidence: SynopsisConfidence


# --- API request/response schemas ------------------------------------------------

AnalysisModule = Literal["go_no_go", "synopsis", "risk_finder"]


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    issuing_authority: str | None = None
    status: DocumentStatus
    total_pages: int | None = None
    uploaded_at: datetime


class DocumentStatusResponse(BaseModel):
    """Extended (docs/DECISIONS.md #60) beyond the original page-level progress with
    chunk/module-level detail — all computed live from existing tables (`chunks`,
    `chunk_extractions`, `document_analysis`), no new tables or columns — so the
    frontend can show real map-pass/reduce-pass progress instead of the document
    appearing to sit motionless during "analyzing".
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: DocumentStatus
    total_pages: int | None = None
    pages_processed: int = 0
    # Split out from total_pages/pages_processed (docs/DECISIONS.md #75/#77) — once a
    # document's hyperlinks are being fetched, pages_processed legitimately exceeds
    # total_pages (which briefly still holds just the uploaded PDF's own count until
    # the fetch stage finishes), which read as a nonsensical ratio in the UI (e.g.
    # "48/6 pages processed"). These two make what's actually happening explicit:
    # how many pages came from the uploaded PDF itself, and how many distinct
    # hyperlinked documents have been found/fetched so far.
    main_document_pages: int = 0
    linked_documents_found: int = 0
    chunks_total: int = 0
    chunks_mapped: int = 0
    modules_ready: list[AnalysisModule] = Field(default_factory=list)
    updated_at: datetime


class DocumentAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    module: AnalysisModule
    result: dict
    model_used: str | None = None
    created_at: datetime


class PageContentResponse(BaseModel):
    """The citation-verification UI's actual payload (docs/SPEC.md's HITL note) — what
    a user sees after clicking a `page_ref`. `has_image` tells the frontend whether to
    also fetch GET .../pages/{page_number}/image, rather than embedding image bytes
    (base64) in this JSON response.
    """

    model_config = ConfigDict(from_attributes=True)

    page_number: int
    classification: PageClassification
    extraction_method: ExtractionMethod | None = None
    raw_text: str | None = None
    confidence_score: float | None = None
    has_image: bool
    # Set when this page's content came from a hyperlink found inside the uploaded
    # PDF rather than the PDF itself (docs/DECISIONS.md) — null for every page of the
    # document actually uploaded.
    source_url: str | None = None


# --- company_profiles — CRUD for the reduce pass's go_no_go input (docs/DECISIONS.md
# #51/#59). Fields match the real DDL exactly (docs/SPEC.md §3.1); the same
# REQUIRED_PROFILE_FIELDS list app.pipeline.reduce_pass checks at analysis time
# (company_name, annual_turnover, certifications, sectors, max_capacity_pct) is not
# re-enforced here — an incomplete profile is valid to *save* (a work in progress,
# same as docs/DECISIONS.md #51's real seed data), it just can't run a full go_no_go
# until it's complete; that check happens where it actually matters, at analysis time. -


class CompanyProfileWrite(BaseModel):
    company_name: str
    annual_turnover: dict | None = None
    certifications: list | None = None
    past_projects: list | None = None
    geographic_presence: list | None = None
    sectors: list | None = None
    max_capacity_pct: float | None = None
    cin: str | None = None
    roc_number: str | None = None
    section8_licence_number: str | None = None
    date_of_incorporation: date | None = None
    pan: str | None = None
    gstin: str | None = None
    udyam_registration_number: str | None = None
    msme_classification: list | None = None
    ngo_darpan_id: str | None = None
    authorised_capital_inr: float | None = None
    paid_up_capital_inr: float | None = None
    net_worth_inr: float | None = None
    turnover_source: str | None = None
    unconfirmed_org_turnover_inr: dict | None = None
    directors: list | None = None
    bank_details: dict | None = None
    employment_count: dict | None = None
    government_grants: list | None = None

    @model_validator(mode="after")
    def _turnover_source_required_with_turnover(self) -> "CompanyProfileWrite":
        # The direct fix for the real problem docs/sutf-company-profile-decision-grade
        # .docx found: two turnover figures on file, no record of which was actually
        # confirmed against this entity. See migration 0003's docstring.
        if self.annual_turnover is not None and self.turnover_source is None:
            raise ValueError(
                "annual_turnover cannot be set without also setting turnover_source "
                "(which document/filing the figures came from)"
            )
        return self


class CompanyProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    annual_turnover: dict | None = None
    certifications: list | None = None
    past_projects: list | None = None
    geographic_presence: list | None = None
    sectors: list | None = None
    max_capacity_pct: float | None = None
    cin: str | None = None
    roc_number: str | None = None
    section8_licence_number: str | None = None
    date_of_incorporation: date | None = None
    pan: str | None = None
    gstin: str | None = None
    udyam_registration_number: str | None = None
    msme_classification: list | None = None
    ngo_darpan_id: str | None = None
    authorised_capital_inr: float | None = None
    paid_up_capital_inr: float | None = None
    net_worth_inr: float | None = None
    turnover_source: str | None = None
    unconfirmed_org_turnover_inr: dict | None = None
    directors: list | None = None
    bank_details: dict | None = None
    employment_count: dict | None = None
    government_grants: list | None = None
    created_at: datetime
    updated_at: datetime
