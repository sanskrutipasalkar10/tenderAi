"""Document upload — POST /documents kicks off the pipeline asynchronously (Celery),
returning immediately per the spec's own priority (completeness over speed, but the API
still shouldn't block on a 1000-page document). GET /documents lists uploads.

Content-type/size checks happen here (cheapest, no PDF parsing needed); everything
that needs to actually open the PDF — corrupt/0-page rejection, the page ceiling, and
the "is this a tender" heuristic — is app.guardrails.input_checks.validate_upload
(Phase 6), called before a Document row is created or anything reaches S3/Celery, so a
rejected upload costs nothing beyond the validation itself.
"""

import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.exceptions import DataQualityError
from app.guardrails.input_checks import validate_upload
from app.models.document import Document
from app.models.schemas import DocumentUploadResponse
from app.storage.objects import upload_pdf
from app.workers.tasks_ingest import ingest_document_task

router = APIRouter(prefix="/documents", tags=["ingestion"])

MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("", response_model=DocumentUploadResponse, status_code=201)
def upload_document(
    file: UploadFile,
    company_profile_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> Document:
    if file.content_type != "application/pdf":
        raise DataQualityError("Only PDF files are accepted")

    pdf_bytes = file.file.read()
    if len(pdf_bytes) == 0:
        raise DataQualityError("Uploaded file is empty")
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise DataQualityError(
            f"File exceeds the {settings.max_upload_size_mb}MB upload limit"
        )
    validate_upload(pdf_bytes)

    document = Document(
        filename=file.filename or "upload.pdf",
        status="uploaded",
        company_profile_id=company_profile_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    document.original_pdf_s3_key = upload_pdf(document.id, pdf_bytes)
    db.commit()
    db.refresh(document)

    ingest_document_task.delay(str(document.id))
    return document


@router.get("", response_model=list[DocumentUploadResponse])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.execute(select(Document).order_by(Document.uploaded_at.desc())).scalars())
