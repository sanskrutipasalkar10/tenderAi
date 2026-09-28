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


@router.post(
    "/{document_id}/analysis/go_no_go/resubmit", response_model=DocumentAnalysisResponse
)
def resubmit_go_no_go(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """"Resubmit analysis" — re-asks the model for fresh factor_scores against the
    document's current, human-reviewed criteria_matches (see
    app.pipeline.reduce_pass.rescore_go_no_go), so score/decision actually move once a
    bid team has finished reviewing insufficient_data/fail criteria via PATCH .../review
    above. Unlike that endpoint, this DOES trigger a real LLM call — a real, synchronous
    reduce-pass call, same as the existing review flow's ~5-8s latency profile
    (docs/DECISIONS.md, tasks_reduce.py), not routed through Celery since it's a single
    user-initiated action, not a fan-out/fan-in pipeline stage.

    Local imports (not module-level) mirror app.workers.tasks_reduce.go_no_go_task's own
    pattern — app.workers.tasks_reduce <-> app.workers.celery_app is a documented
    circular import via tasks_pipeline (tests/unit/test_tasks_reduce_profile_dict.py),
    and importing lazily here avoids the same fragility rather than risking hitting it
    at FastAPI startup.
    """
    from app.models.company_profile import CompanyProfile
    from app.models.document import Document
    from app.pipeline.reduce_pass import rescore_go_no_go
    from app.workers.tasks_reduce import profile_to_dict

    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    profile = (
        db.get(CompanyProfile, document.company_profile_id)
        if document.company_profile_id
        else None
    )
    return rescore_go_no_go(db, document, profile_to_dict(profile))
