"""Ingestion orchestration — classify + extract (native or vision) every page, dedupe
against boilerplate_cache, and write the raw layer (`pages`, `extracted_tables`).
Vision extraction is the only LLM call in this module, routed through
app.llm.router/client, never a provider SDK directly (CLAUDE.md hard rule 1).

Kept as plain, directly-callable functions rather than Celery-task methods so they're
testable without a broker (`app/workers/tasks_ingest.py` is a thin wrapper around
`run_ingestion`, per the FastAPI playbook's "keep business logic out of the task
definition" pattern). Plain `def`, not `async def` — PyMuPDF/pdfplumber and boto3 are
CPU-bound / blocking (CLAUDE.md hard rule 9).

Every page produces a `pages` row regardless of extraction outcome — CLAUDE.md's
zero-page-drop invariant: an extraction failure (native finds no text, vision errors
out) is a low-confidence row, never a missing one.
"""

import uuid

import fitz
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.document import Document
from app.models.extracted_table import ExtractedTable
from app.models.page import Page
from app.pipeline import dedupe
from app.pipeline.classify import classification_confidence, classify_page
from app.pipeline.extract_native import extract_page_text, extract_table_structure
from app.pipeline.extract_vision import extract_page_via_vision
from app.storage.objects import get_object_bytes

logger = get_logger(__name__)

NATIVE_EXTRACTABLE_CLASSIFICATIONS = {"native_text", "table", "mixed"}


def run_ingestion(db: Session, document_id: uuid.UUID) -> Document:
    """Runs classification + native extraction for every page of an already-uploaded
    document (its PDF must already be in S3 at `document.original_pdf_s3_key`).
    """
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")
    if not document.original_pdf_s3_key:
        raise ValueError(f"Document {document_id} has no uploaded PDF to process")

    document.status = "classifying"
    db.commit()

    pdf_bytes = get_object_bytes(document.original_pdf_s3_key)
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")

    document.status = "extracting"
    document.total_pages = pdf.page_count
    db.commit()

    for page in pdf:
        _process_page(db, document, page, pdf_bytes)

    pdf.close()

    document.status = "extracted"
    db.commit()
    db.refresh(document)
    logger.info(
        "ingestion.completed", document_id=str(document.id), total_pages=document.total_pages
    )
    return document


def _process_page(db: Session, document: Document, page: fitz.Page, pdf_bytes: bytes) -> None:
    classification = classify_page(page)
    confidence = classification_confidence(page, classification)

    raw_text: str | None = None
    content_hash: str | None = None
    extraction_method: str | None = None

    if classification in NATIVE_EXTRACTABLE_CLASSIFICATIONS:
        result = extract_page_text(page)
        raw_text = result.raw_text
        content_hash = result.content_hash
        extraction_method = "native" if raw_text is not None else None
    else:  # scanned_image
        result = extract_page_via_vision(page)
        raw_text = result.raw_text
        content_hash = result.content_hash
        extraction_method = result.extraction_method
        confidence = result.confidence_score

    page_row = Page(
        document_id=document.id,
        page_number=page.number,
        classification=classification,
        extraction_method=extraction_method,
        raw_text=raw_text,
        content_hash=content_hash,
        confidence_score=confidence,
    )
    db.add(page_row)
    db.flush()  # populate page_row.id (server-generated) before it's referenced below

    if classification == "table":
        table = extract_table_structure(pdf_bytes, page.number)
        if table is not None:
            db.add(
                ExtractedTable(
                    page_id=page_row.id,
                    # classifying BOQ/schedule/eligibility-matrix is a later refinement
                    table_type=None,
                    table_data=table.model_dump(),
                )
            )

    db.commit()

    if raw_text is not None and content_hash is not None:
        dedupe.check_and_record(
            db, content_hash, document.id, raw_text, document.issuing_authority
        )
