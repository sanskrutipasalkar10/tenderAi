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
    # uploaded PDF itself has both source_url and attachment_id IS NULL; a page
    # fetched from a hyperlink or a manually-attached supporting document doesn't.
    # All computed live from `pages`, same pattern as pages_processed above — no new
    # table.
    main_document_pages = db.execute(
        select(func.count())
        .select_from(Page)
        .where(
            Page.document_id == document_id,
            Page.source_url.is_(None),
            Page.attachment_id.is_(None),
        )
    ).scalar_one()
    linked_documents_found = db.execute(
        select(func.count(func.distinct(Page.source_url)))
        .select_from(Page)
        .where(Page.document_id == document_id, Page.source_url.isnot(None))
    ).scalar_one()
    attachments_processed = db.execute(
        select(func.count(func.distinct(Page.attachment_id)))
        .select_from(Page)
        .where(Page.document_id == document_id, Page.attachment_id.isnot(None))
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
    # Of chunks_mapped above, how many skipped the LLM call entirely (duplicate
    # content already seen elsewhere, app.pipeline.map_pass_cache) — computed live
    # from the same join, same pattern as chunks_mapped itself.
    chunks_deduped = db.execute(
        select(func.count())
        .select_from(ChunkExtraction)
        .join(Chunk, ChunkExtraction.chunk_id == Chunk.id)
        .where(Chunk.document_id == document_id, ChunkExtraction.reused_from_chunk_id.isnot(None))
    ).scalar_one()
    modules_ready = list(
        db.execute(
            select(DocumentAnalysis.module).where(DocumentAnalysis.document_id == document_id)
        ).scalars()
    )

    return DocumentStatusResponse(
        id=document.id,
        filename=document.filename,
        # Document.status is a plain `str` column; the DB CHECK constraint (migration
        # 0001) is what actually guarantees it's one of DocumentStatus's values.
        status=cast(DocumentStatus, document.status),
        total_pages=document.total_pages,
        pages_processed=pages_processed,
        main_document_pages=main_document_pages,
        linked_documents_found=linked_documents_found,
        attachments_processed=attachments_processed,
        chunks_total=chunks_total,
        chunks_mapped=chunks_mapped,
        chunks_deduped=chunks_deduped,
        modules_ready=cast(list[AnalysisModule], modules_ready),
        failure_reason=document.failure_reason,
        updated_at=document.updated_at,
    )


@router.post("/{document_id}/cancel", response_model=DocumentStatusResponse)
def cancel_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """User-initiated stop. Sets status="failed" with a "Cancelled by user" reason —
    reuses the existing terminal state rather than a new "cancelled" enum value/
    migration, since nothing downstream needs to distinguish the two.

    This only ever *requests* a stop — Celery runs `--pool=solo` here (one task at a
    time, no separate process per task), so an already-running task can't be forcibly
    interrupted; every pipeline task checks this status at its own next entry point
    instead (app.workers._failure.not_cancelled) and no-ops if it's already set. A
    task mid-flight right now will still finish that one step before noticing.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status in ("ready", "failed"):
        raise HTTPException(
            status_code=409, detail=f"Document is already {document.status}, nothing to cancel"
        )
    document.status = "failed"
    document.failure_reason = "Cancelled by user"
    db.commit()
    return get_document_status(document_id, db)
