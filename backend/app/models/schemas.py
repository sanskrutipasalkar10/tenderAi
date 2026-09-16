"""Pydantic schemas for API request/response bodies and internal pipeline data.

Kept separate from the SQLAlchemy ORM models in this package (never return ORM objects
directly from routes — FastAPI playbook Phase 3) and from the LLM-facing schemas in
app/prompts (which validate model output, not internal pipeline handoffs).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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


class MapPassResult(BaseModel):
    dates: list[MapPassDateFact] = Field(default_factory=list)
    amounts: list[MapPassAmountFact] = Field(default_factory=list)
    criteria: list[MapPassCriterionFact] = Field(default_factory=list)
    risk_candidates: list[MapPassRiskCandidate] = Field(default_factory=list)


# --- Reduce-pass output (app/pipeline/reduce_pass.py) — validates each module's model
# response before it's trusted (hard rule 4). Severity (risk_finder) and decision/score
# (go_no_go) are deliberately NOT part of what the model returns — CLAUDE.md hard rule 3
# ("score-formula math are code, not prompt instructions") and the plan's own open
# decision ("risk severity thresholds... encode as an explicit rubric, not model
# discretion") — reduce_pass.py computes both in code from the model's more narrowly
# interpretive output (which criteria pass/fail, which clause is which risk category). --


GoNoGoStatus = Literal["pass", "fail"]
GoNoGoDecision = Literal["Go", "Conditional-Go", "No-Go"]
RiskSeverity = Literal["HIGH", "MEDIUM", "LOW"]
SynopsisConfidence = Literal["high", "medium", "low"]


class GoNoGoCriterionMatch(BaseModel):
    criterion: str
    required: str
    company_value: str
    status: GoNoGoStatus
    page_ref: int = Field(ge=0)


class GoNoGoLLMResult(BaseModel):
    """What the model returns for go_no_go — criteria comparison only. `decision`,
    `score`, and `gaps` are computed by reduce_pass.py from this, never asked of the
    model directly.
    """

    criteria_matches: list[GoNoGoCriterionMatch] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class GoNoGoResult(BaseModel):
    """The full go_no_go document_analysis.result shape (docs/SPEC.md §6)."""

    score: int = Field(ge=0, le=100)
    decision: GoNoGoDecision
    criteria_matches: list[GoNoGoCriterionMatch] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


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


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    status: DocumentStatus
    total_pages: int | None = None
    uploaded_at: datetime


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: DocumentStatus
    total_pages: int | None = None
    pages_processed: int = 0
    updated_at: datetime


AnalysisModule = Literal["go_no_go", "synopsis", "risk_finder"]


class DocumentAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    module: AnalysisModule
    result: dict
    model_used: str | None = None
    created_at: datetime
