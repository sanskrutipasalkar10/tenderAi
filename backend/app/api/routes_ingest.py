"""Document upload — POST /documents kicks off the pipeline asynchronously (Celery),
returning immediately per the spec's own priority (completeness over speed, but the API
still shouldn't block on a 1000-page document). GET /documents lists uploads.

Content-type/size checks happen here (cheapest, no PDF parsing needed); everything
that needs to actually open the PDF — corrupt/0-page rejection, the page ceiling, and
the "is this a tender" heuristic — is app.guardrails.input_checks.validate_upload
(Phase 6), called before a Document row is created or anything reaches S3/Celery, so a
rejected upload costs nothing beyond the validation itself.

Optional `attachments` (docs/DECISIONS.md — migration 0005) let a user bundle
supporting documents (a company certificate, a past-project reference) in at the same
time as the primary tender PDF — upload-time only, confirmed with the user, not a
general "attach anytime" flow. Each goes through the lighter validate_attachment (basic
PDF sanity, deliberately not the "is this a tender" heuristic — a supporting document
legitimately isn't a tender itself) and is stored as its own `document_attachments` row;
`app.services.ingestion.run_ingestion` picks them up and appends their pages to the
same document, continuing the page_number sequence exactly like a fetched hyperlink.
"""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.exceptions import DataQualityError
from app.guardrails.input_checks import validate_attachment, validate_upload
from app.models.document import Document
from app.models.document_attachment import DocumentAttachment
from app.models.schemas import DocumentUploadResponse
from app.storage.objects import upload_attachment_pdf, upload_pdf
from app.workers.tasks_pipeline import enqueue_full_pipeline

router = APIRouter(prefix="/documents", tags=["ingestion"])

MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("", response_model=DocumentUploadResponse, status_code=201)
def upload_document(
    file: UploadFile,
    company_profile_id: uuid.UUID | None = None,
    attachments: list[UploadFile] = File(default=[]),
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

    # A file <input multiple> with nothing selected can still submit one empty part
    # (empty filename, zero bytes) rather than an empty list — skip those rather than
    # rejecting the whole upload over a browser form-encoding quirk.
    attachment_payloads: list[tuple[str, bytes]] = []
    for attachment in attachments:
        if not attachment.filename:
            continue
        if attachment.content_type != "application/pdf":
            raise DataQualityError(
                f"Supporting document '{attachment.filename}' must be a PDF"
            )
        attachment_bytes = attachment.file.read()
        if len(attachment_bytes) == 0:
            raise DataQualityError(f"Supporting document '{attachment.filename}' is empty")
        if len(attachment_bytes) > MAX_UPLOAD_BYTES:
            raise DataQualityError(
                f"Supporting document '{attachment.filename}' exceeds the "
                f"{settings.max_upload_size_mb}MB upload limit"
            )
        validate_attachment(attachment_bytes)
        attachment_payloads.append((attachment.filename, attachment_bytes))

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

    for filename, attachment_bytes in attachment_payloads:
        # Generated client-side (rather than the DB's gen_random_uuid() default) so
        # the S3 key is known before the row is ever inserted — s3_key is NOT NULL,
        # so a flush-then-fill-in-the-key approach would violate that constraint at
        # insert time.
        attachment_id = uuid.uuid4()
        s3_key = upload_attachment_pdf(document.id, attachment_id, attachment_bytes)
        db.add(
            DocumentAttachment(
                id=attachment_id, document_id=document.id, filename=filename, s3_key=s3_key
            )
        )
    db.commit()

    enqueue_full_pipeline(str(document.id))
    return document


@router.get("", response_model=list[DocumentUploadResponse])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.execute(select(Document).order_by(Document.uploaded_at.desc())).scalars())
