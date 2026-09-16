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
