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

After the uploaded PDF's own pages, ingestion appends two further kinds of content as
more `pages` rows on the SAME document, continuing the page_number sequence: any
manually-attached supporting documents (docs/DECISIONS.md — migration 0005, upload-time
only), then a hyperlink-walking stage (docs/DECISIONS.md) — real GeM tender cover
sheets link out to the actual tender content ("...AS PER ANNEXURE A ENCLOSED" where
Annexure A is a URL, not an attachment) — appending whatever it can fetch. A link that
can't be fetched (guardrail rejection, timeout, unparseable content) is logged and
skipped, never fails the whole ingestion task.
"""

import uuid

import fitz
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.document import Document
from app.models.document_attachment import DocumentAttachment
from app.models.extracted_table import ExtractedTable
from app.models.page import Page
from app.models.schemas import PageExtractionResult
from app.pipeline import dedupe, fetch_links
from app.pipeline.classify import classification_confidence, classify_page
from app.pipeline.extract_native import extract_page_text, extract_table_structure
from app.pipeline.extract_vision import extract_page_via_vision
from app.storage.objects import get_object_bytes

logger = get_logger(__name__)

NATIVE_EXTRACTABLE_CLASSIFICATIONS = {"native_text", "table", "mixed"}


def run_ingestion(db: Session, document_id: uuid.UUID) -> Document:
    """Runs classification + native extraction for every page of an already-uploaded
    document (its PDF must already be in S3 at `document.original_pdf_s3_key`), then
    walks and fetches its hyperlinks (docs/DECISIONS.md), appending whatever real
    tender content they resolve to as more pages on the same document.
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
        _process_page(db, document, page.number, page, pdf_bytes, source_url=None)

    next_page_number = pdf.page_count
    next_page_number = _process_attachments(db, document, next_page_number)
    next_page_number = _process_linked_documents(db, document, pdf, next_page_number)
    pdf.close()

    # Critical: must reflect the FINAL combined page count (cover pages + every
    # appended linked-doc page) before build_chunks runs later in the pipeline chain —
    # build_chunks derives its own chunk spans from the real persisted `pages` rows
    # (app.pipeline.chunk._source_spans), but total_pages is also what drives the
    # status/progress display (routes_status.py's pages_processed/total_pages), so it
    # must stay accurate here regardless.
    document.total_pages = next_page_number

    document.status = "extracted"
    db.commit()
    db.refresh(document)
    logger.info(
        "ingestion.completed", document_id=str(document.id), total_pages=document.total_pages
    )
    return document


def _classify_and_extract(page: fitz.Page) -> PageExtractionResult:
    """The classify+extract+confidence core, shared between the uploaded PDF's own
    pages and every page of a fetched linked document — identical treatment either
    way, since a linked annexure is real tender content, not a lesser source.
    """
    classification = classify_page(page)
    confidence = classification_confidence(page, classification)

    if classification in NATIVE_EXTRACTABLE_CLASSIFICATIONS:
        result = extract_page_text(page)
        extraction_method = "native" if result.raw_text is not None else None
        return result.model_copy(
            update={"classification": classification, "extraction_method": extraction_method,
                    "confidence_score": confidence}
        )

    result = extract_page_via_vision(page)  # scanned_image
    return result.model_copy(update={"classification": classification})


def _persist_page(
    db: Session,
    document: Document,
    page_number: int,
    result: PageExtractionResult,
    *,
    source_url: str | None,
    attachment_id: uuid.UUID | None,
    table_source_bytes: bytes | None,
    table_source_page_number: int | None,
) -> None:
    """Writes one `pages` row (+ `extracted_tables` row if applicable) and runs the
    boilerplate dedupe check — shared by the cover PDF's own pages, every appended
    linked-document page, and every appended supporting-attachment page.
    `table_source_bytes`/`table_source_page_number` are the PDF bytes and LOCAL page
    index extract_table_structure needs — for a linked/attached PDF's table page these
    are that PDF's own bytes/index, never the cover PDF's, since extract_table_structure
    reopens the PDF itself via pdfplumber rather than reusing a fitz.Page handle.
    """
    page_row = Page(
        document_id=document.id,
        page_number=page_number,
        classification=result.classification,
        extraction_method=result.extraction_method,
        raw_text=result.raw_text,
        content_hash=result.content_hash,
        confidence_score=result.confidence_score,
        source_url=source_url,
        attachment_id=attachment_id,
    )
    db.add(page_row)
    db.flush()  # populate page_row.id (server-generated) before it's referenced below

    if result.classification == "table" and table_source_bytes is not None:
        table = extract_table_structure(table_source_bytes, table_source_page_number or 0)
        if table is not None:
            db.add(
                ExtractedTable(
                    page_id=page_row.id,
                    table_type=None,
                    table_data=table.model_dump(),
                )
            )

    db.commit()

    if result.raw_text is not None and result.content_hash is not None:
        dedupe.check_and_record(
            db, result.content_hash, document.id, result.raw_text, document.issuing_authority
        )


def _process_page(
    db: Session,
    document: Document,
    page_number: int,
    page: fitz.Page,
    pdf_bytes: bytes,
    *,
    source_url: str | None,
) -> None:
    result = _classify_and_extract(page)
    _persist_page(
        db, document, page_number, result,
        source_url=source_url,
        attachment_id=None,
        table_source_bytes=pdf_bytes,
        table_source_page_number=page.number,
    )


def _process_attachments(db: Session, document: Document, next_page_number: int) -> int:
    """Extracts every manually-attached supporting document (docs/DECISIONS.md —
    migration 0005, upload-time only), appending their pages after the cover PDF's own
    pages and before any hyperlink-fetched content. Each attachment's pages form their
    own contiguous span (app.pipeline.chunk._source_spans keys on attachment_id too),
    so a map-pass chunk never straddles the boundary between the tender and a
    supporting document. Unlike a hyperlink fetch, an attachment was uploaded by the
    user directly — there's nothing to fetch or fail here beyond opening the PDF
    already validated and stored at upload time.
    """
    attachments = (
        db.query(DocumentAttachment)
        .filter(DocumentAttachment.document_id == document.id)
        .order_by(DocumentAttachment.created_at)
        .all()
    )
    for attachment in attachments:
        pdf_bytes = get_object_bytes(attachment.s3_key)
        attachment_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page in attachment_pdf:
                result = _classify_and_extract(page)
                _persist_page(
                    db, document, next_page_number, result,
                    source_url=None,
                    attachment_id=attachment.id,
                    table_source_bytes=pdf_bytes,
                    table_source_page_number=page.number,
                )
                next_page_number += 1
        finally:
            attachment_pdf.close()
    return next_page_number


def _process_linked_documents(
    db: Session, document: Document, cover_pdf: fitz.Document, next_page_number: int
) -> int:
    """Extracts every hyperlink from `cover_pdf`, fetches/caches what it can, and
    appends the results as more `pages` rows continuing the page_number sequence.
    Returns the final page_number count. Never raises for an individual link failure
    (guardrail rejection, timeout, unparseable content) — logged and skipped, matching
    the graceful-degradation contract already established for secondary pipeline
    calls (e.g. reduce_pass's _run_pq_checklist/_run_tq_scoring).
    """
    refs = fetch_links.extract_uri_links(cover_pdf)
    processed = 0

    for ref in refs:
        if processed >= settings.linked_doc_max_per_document:
            logger.warning(
                "ingestion.linked_doc_limit_reached",
                document_id=str(document.id),
                limit=settings.linked_doc_max_per_document,
            )
            break

        # table_source_bytes stays None for a cache hit — a cache hit restores
        # classification/raw_text/confidence but not table structure, a deliberate,
        # documented scope decision (docs/DECISIONS.md): table extraction only runs
        # on a fresh fetch, never re-derived from the cache.
        table_source_bytes: bytes | None = None

        cached_pages = fetch_links.get_cached_pages(db, ref.url)
        if cached_pages is not None:
            page_results = cached_pages
        else:
            resolved = fetch_links.resolve_linked_document(ref.url)
            if resolved is None:
                logger.warning(
                    "ingestion.linked_doc_unreachable", document_id=str(document.id), url=ref.url
                )
                continue

            if resolved.kind == "pdf":
                page_results = []
                linked_pdf = fitz.open(stream=resolved.pdf_bytes, filetype="pdf")
                try:
                    for lpage in linked_pdf:
                        page_results.append(_classify_and_extract(lpage))
                finally:
                    linked_pdf.close()
                table_source_bytes = resolved.pdf_bytes
            else:
                page_results = [fetch_links.text_to_page_record(resolved.plain_text)]

            # Boilerplate links (General Terms & Conditions etc.) reuse the same URL
            # across many different tenders — cache once, reused on every future
            # document that references it. Bid-specific links are never cached (no
            # value in caching a URL only ever used once).
            if fetch_links.is_boilerplate(ref.url):
                fetch_links.store_cached_pages(db, ref.url, document.id, page_results)

        for local_index, result in enumerate(page_results):
            _persist_page(
                db, document, next_page_number, result,
                source_url=ref.url,
                attachment_id=None,
                table_source_bytes=table_source_bytes,
                table_source_page_number=local_index,
            )
            next_page_number += 1

        processed += 1

    return next_page_number
