"""Serves already-computed document_analysis rows — GET only, never triggers a reduce
pass itself (that runs via app.workers.tasks_reduce, kicked off by the pipeline
orchestrator once it exists). A 404 here means "not analyzed yet," not "run it now."
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.guardrails.output_checks import validate_analysis_result
from app.models.schemas import AnalysisModule, DocumentAnalysisResponse, GoNoGoReviewRequest
from app.pipeline.reduce_pass import apply_human_overrides
from app.services import analysis_reader

router = APIRouter(prefix="/documents", tags=["analysis"])


@router.get("/{document_id}/analysis/{module}", response_model=DocumentAnalysisResponse)
def get_document_analysis(
    document_id: uuid.UUID, module: AnalysisModule, db: Session = Depends(get_db)
):
    analysis = analysis_reader.get_analysis(db, document_id, module)
    if analysis is None:
        raise HTTPException(
            status_code=404, detail=f"No {module} analysis found for this document yet"
        )
    return analysis


@router.get("/{document_id}/analysis", response_model=list[DocumentAnalysisResponse])
def list_document_analysis(document_id: uuid.UUID, db: Session = Depends(get_db)):
    return analysis_reader.get_all_analysis(db, document_id)


@router.patch(
    "/{document_id}/analysis/go_no_go/review", response_model=DocumentAnalysisResponse
)
def review_go_no_go(
    document_id: uuid.UUID, request: GoNoGoReviewRequest, db: Session = Depends(get_db)
):
    """Human review of specific "eligibility" criteria on an already-computed go_no_go
    analysis (see app.pipeline.reduce_pass.apply_human_overrides) — never triggers a
    new LLM call, only recomputes decision/gaps/score from the effective statuses.
    """
    analysis = analysis_reader.get_analysis(db, document_id, "go_no_go")
    if analysis is None:
        raise HTTPException(
            status_code=404, detail="No go_no_go analysis found for this document yet"
        )

    overrides = [(o.criterion_index, o.status, o.note) for o in request.overrides]
    updated_result = apply_human_overrides(analysis.result, overrides)
    analysis.result = validate_analysis_result("go_no_go", updated_result)
    db.commit()
    db.refresh(analysis)
    return analysis
