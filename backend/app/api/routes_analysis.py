"""Serves already-computed document_analysis rows — GET only, never triggers a reduce
pass itself (that runs via app.workers.tasks_reduce, kicked off by the pipeline
orchestrator once it exists). A 404 here means "not analyzed yet," not "run it now."
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.email import send_review_notification
from app.guardrails.output_checks import validate_analysis_result
from app.models.schemas import (
    AnalysisModule,
    DocumentAnalysisResponse,
    DocumentUploadResponse,
    GoNoGoReviewRequest,
)
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

    Marking a criterion "pass" (eligible) fires an email notification
    (app.core.email, docs/DECISIONS.md) flagging the gap for manual entry into the
    company profile — a reviewer overriding the model's read means the company
    profile is missing information the tender required, and without this the same gap
    recurs on every future tender. "fail" overrides don't notify: they agree with or
    confirm a likely-correct read, not surface a data gap.
    """
    analysis = analysis_reader.get_analysis(db, document_id, "go_no_go")
    if analysis is None:
        raise HTTPException(
            status_code=404, detail="No go_no_go analysis found for this document yet"
        )

    original_matches = analysis.result.get("criteria_matches", [])
    overrides = [(o.criterion_index, o.status, o.note) for o in request.overrides]
    updated_result = apply_human_overrides(analysis.result, overrides)
    analysis.result = validate_analysis_result("go_no_go", updated_result)
    db.commit()
    db.refresh(analysis)

    # Only after the override is confirmed valid and saved — never for one
    # apply_human_overrides would have rejected (an out-of-range index or a
    # procedural criterion, which raises before this point is ever reached).
    for override in request.overrides:
        if override.status == "pass" and 0 <= override.criterion_index < len(original_matches):
            match = original_matches[override.criterion_index]
            send_review_notification(
                document_id=str(document_id),
                criterion=match.get("criterion", ""),
                required=match.get("required", ""),
                company_value=match.get("company_value", ""),
                reviewer_note=override.note,
            )

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


@router.post("/{document_id}/reevaluate", response_model=DocumentUploadResponse)
def reevaluate_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Dashboard "Reevaluate" action — re-runs all three reduce-pass modules (go_no_go,
    synopsis, risk_finder) against a document's existing extracted facts, for when the
    company profile or reduce-pass prompts/logic have changed since it was last
    analyzed. Unlike resubmit_go_no_go above, this is routed through Celery
    (app.workers.tasks_pipeline.enqueue_reevaluation), not run synchronously: it's 3
    real LLM calls in sequence, the same work the pipeline's own reduce stage does, and
    that stage has taken several minutes in practice — too slow to hold an HTTP request
    open for.

    Only allowed from status="ready" — the only terminal "finished" state the pipeline
    actually sets today — so this never races with a first-time analysis still in
    flight. Also requires at least one chunk to exist, since the reduce pass reads from
    chunk_extractions and has nothing to work from otherwise.

    Deletes the document's existing document_analysis rows before re-enqueueing, rather
    than leaving them in place for _upsert_analysis to overwrite in place once each
    module finishes. Found in practice: with the old rows left sitting there,
    modules_ready (DocumentStatusResponse, computed live as "distinct document_analysis
    rows for this document") reads 3/3 for the entire reevaluation, since the stale
    rows already satisfy that count — the frontend's processing-progress UI
    (ProcessingPipeline/ProcessingLog) only renders a line when a number climbs from
    its previous poll, so it had nothing to show climbing and looked permanently
    "already done." Clearing them first means modules_ready genuinely goes back to 0
    and climbs to 3 as the new results land, the same way it does on a first-time run —
    no frontend change needed, the existing progress UI already does the right thing
    once the backend state actually reflects "not yet re-analyzed."
    """
    from sqlalchemy import delete

    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.document_analysis import DocumentAnalysis
    from app.workers.tasks_pipeline import enqueue_reevaluation

    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot reevaluate a document with status '{document.status}' - it "
                "must have completed its first analysis pass (status 'ready') first."
            ),
        )
    has_chunks = db.execute(
        select(Chunk.id).where(Chunk.document_id == document_id).limit(1)
    ).first()
    if has_chunks is None:
        raise HTTPException(
            status_code=409,
            detail="This document has no extracted content to re-evaluate.",
        )

    db.execute(delete(DocumentAnalysis).where(DocumentAnalysis.document_id == document_id))
    document.status = "analyzing"
    db.commit()
    db.refresh(document)
    enqueue_reevaluation(str(document_id))
    return document
