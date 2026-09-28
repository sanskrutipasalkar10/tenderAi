import uuid
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.page import Page
from app.models.schemas import AnalysisModule, DocumentStatus, DocumentStatusResponse

router = APIRouter(prefix="/documents", tags=["ingestion"])


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    pages_processed = db.execute(
        select(func.count()).select_from(Page).where(Page.document_id == document_id)
    ).scalar_one()

    # Split from pages_processed (docs/DECISIONS.md #75/#77) — a page from the
    # uploaded PDF itself has source_url IS NULL; a page fetched from a hyperlink
    # found inside it doesn't. Both computed live from `pages`, same pattern as
    # pages_processed above — no new table, no new column.
    main_document_pages = db.execute(
        select(func.count())
        .select_from(Page)
        .where(Page.document_id == document_id, Page.source_url.is_(None))
    ).scalar_one()
    linked_documents_found = db.execute(
        select(func.count(func.distinct(Page.source_url)))
        .select_from(Page)
        .where(Page.document_id == document_id, Page.source_url.isnot(None))
    ).scalar_one()

    # Chunk/module progress — computed live from existing tables (docs/DECISIONS.md
    # #60), not a separate progress table, so this stays accurate even if a worker
    # restarts mid-document: the real chunk_extractions/document_analysis rows are the
    # only source of truth.
    chunks_total = db.execute(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
    ).scalar_one()
    chunks_mapped = db.execute(
        select(func.count())
        .select_from(ChunkExtraction)
        .join(Chunk, ChunkExtraction.chunk_id == Chunk.id)
        .where(Chunk.document_id == document_id)
    ).scalar_one()
    modules_ready = list(
        db.execute(
            select(DocumentAnalysis.module).where(DocumentAnalysis.document_id == document_id)
        ).scalars()
    )

    return DocumentStatusResponse(
        id=document.id,
        # Document.status is a plain `str` column; the DB CHECK constraint (migration
        # 0001) is what actually guarantees it's one of DocumentStatus's values.
        status=cast(DocumentStatus, document.status),
        total_pages=document.total_pages,
        pages_processed=pages_processed,
        main_document_pages=main_document_pages,
        linked_documents_found=linked_documents_found,
        chunks_total=chunks_total,
        chunks_mapped=chunks_mapped,
        modules_ready=cast(list[AnalysisModule], modules_ready),
        updated_at=document.updated_at,
    )
