import uuid
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.document import Document
from app.models.page import Page
from app.models.schemas import DocumentStatus, DocumentStatusResponse

router = APIRouter(prefix="/documents", tags=["ingestion"])


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    pages_processed = db.execute(
        select(func.count()).select_from(Page).where(Page.document_id == document_id)
    ).scalar_one()

    return DocumentStatusResponse(
        id=document.id,
        # Document.status is a plain `str` column; the DB CHECK constraint (migration
        # 0001) is what actually guarantees it's one of DocumentStatus's values.
        status=cast(DocumentStatus, document.status),
        total_pages=document.total_pages,
        pages_processed=pages_processed,
        updated_at=document.updated_at,
    )
