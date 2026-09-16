"""Serves already-computed document_analysis rows — GET only, never triggers a reduce
pass itself (that runs via app.workers.tasks_reduce, kicked off by the pipeline
orchestrator once it exists). A 404 here means "not analyzed yet," not "run it now."
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.schemas import AnalysisModule, DocumentAnalysisResponse
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
