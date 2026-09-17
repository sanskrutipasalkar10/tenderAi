"""Serves one page's content — what the citation-verification UI (docs/SPEC.md's HITL
note) actually shows when a user clicks a `page_ref`. Read-only, same as
routes_analysis.py: never triggers extraction itself, a 404 means "no such page,"
not "not extracted yet."
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.page import Page
from app.models.schemas import PageContentResponse
from app.storage.objects import get_object_bytes

router = APIRouter(prefix="/documents", tags=["pages"])


def _get_page(db: Session, document_id: uuid.UUID, page_number: int) -> Page:
    page = (
        db.query(Page)
        .filter(Page.document_id == document_id, Page.page_number == page_number)
        .first()
    )
    if page is None:
        raise HTTPException(status_code=404, detail="No such page for this document")
    return page


@router.get("/{document_id}/pages/{page_number}", response_model=PageContentResponse)
def get_page_content(
    document_id: uuid.UUID, page_number: int, db: Session = Depends(get_db)
) -> PageContentResponse:
    page = _get_page(db, document_id, page_number)
    return PageContentResponse(
        page_number=page.page_number,
        classification=page.classification,  # type: ignore[arg-type]
        extraction_method=page.extraction_method,  # type: ignore[arg-type]
        raw_text=page.raw_text,
        confidence_score=page.confidence_score,
        has_image=page.image_s3_key is not None,
    )


@router.get("/{document_id}/pages/{page_number}/image")
def get_page_image(document_id: uuid.UUID, page_number: int, db: Session = Depends(get_db)):
    page = _get_page(db, document_id, page_number)
    if page.image_s3_key is None:
        raise HTTPException(status_code=404, detail="This page has no rendered image")
    image_bytes = get_object_bytes(page.image_s3_key)
    return Response(content=image_bytes, media_type="image/png")
