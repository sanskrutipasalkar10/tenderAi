"""Hyperlinked-document handling for GeM-style tenders (docs/DECISIONS.md) — a GeM
cover sheet routinely says "TERMS AND CONDITIONS AND SCOPE OF WORK AS PER ANNEXURE A
ENCLOSED" while Annexure A is a clickable URI, not an embedded attachment
(`doc.embfile_count() == 0` on every real sample checked). This module extracts those
links, classifies them, fetches+extracts their real content, and caches boilerplate
ones (reused across many different tenders) by URL — never by content_hash, a
different identity than app.pipeline.dedupe's existing cache.

Every fetch is gated by app.guardrails.link_checks.is_fetchable_url first (hard rule 6,
generalized to network-fetch-injection) and follows the same bounded-retry-with-
backoff-and-jitter pattern already established for the Ollama call in app.llm.client
(hard rule 10).
"""

import hashlib
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Literal

import fitz
import requests
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.guardrails.link_checks import is_fetchable_url
from app.models.linked_document_cache import LinkedDocumentCache
from app.models.schemas import PageExtractionResult

logger = get_logger(__name__)

DEFAULT_NUM_RETRIES = 1
LinkClassification = Literal["bid_specific", "boilerplate", "unknown"]
SniffedContentType = Literal["pdf", "docx", "html", "unknown"]


@dataclass(frozen=True)
class LinkedDocRef:
    url: str
    text_near_link: str
    page_number: int  # which page of the SOURCE pdf the link was found on


@dataclass(frozen=True)
class LinkedDocumentContent:
    """What resolve_linked_document returns — either an openable PDF's raw bytes (the
    caller feeds each page through the same classify/extract machinery the cover PDF's
    own pages use) or already-extracted plain text from an HTML/docx link (which has no
    page concept of its own, so it becomes a single synthetic page).
    """

    source_url: str
    kind: Literal["pdf", "text"]
    pdf_bytes: bytes | None = None
    plain_text: str | None = None


# --- link extraction + classification (pure, no I/O) -------------------------------


def extract_uri_links(doc: fitz.Document) -> list[LinkedDocRef]:
    """Walks every page's links, keeps URI-kind entries only, deduped by URL (the same
    link — e.g. the General Terms & Conditions footer link — often repeats across
    several pages of the cover sheet; fetching it once is enough).
    """
    refs: list[LinkedDocRef] = []
    seen_urls: set[str] = set()
    for page in doc:
        for link in page.get_links():
            if link.get("kind") != fitz.LINK_URI:
                continue
            url = link.get("uri")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            text = page.get_textbox(fitz.Rect(link["from"])).strip()
            refs.append(LinkedDocRef(url=url, text_near_link=text, page_number=page.number))
    return refs


# Confirmed against 3 real GeM-Bidding-*.pdf files' actual linked URLs — boilerplate
# links carry no bid-specific identifier at all, or point at a portal-wide, date-
# versioned policy document; bid-specific links always carry a bid/contract ID in the
# path.
_BOILERPLATE_URL_MARKERS = (
    "admin.gem.gov.in/apis/v1/gtc/",
    "assets-bg.gem.gov.in",
    "bidplus.gem.gov.in/bidding/downloadomppdfile/",
)
_BID_SPECIFIC_URL_MARKERS = (
    "/biddoc/bid-",
    "/downloadmsemiidoc/",
    "/bidding/bid/bidsla/",
    "fulfilment.gem.gov.in/contract/slafds",
)


def classify_link(url: str) -> LinkClassification:
    lowered = url.lower()
    if any(marker in lowered for marker in _BOILERPLATE_URL_MARKERS):
        return "boilerplate"
    if any(marker in lowered for marker in _BID_SPECIFIC_URL_MARKERS):
        return "bid_specific"
    logger.warning("fetch_links.unrecognized_url_pattern", url=url)
    return "unknown"


# --- fetching ------------------------------------------------------------------------


def _sniff_content_type(content: bytes) -> SniffedContentType:
    """Never trust the URL's apparent purpose or the response header alone — a real
    GeM "Service Level Agreement" link returned a full text/html portal page, not a
    document, confirmed by direct inspection."""
    if content.startswith(b"%PDF-"):
        return "pdf"
    if content[:4] == b"PK\x03\x04":
        return "docx"
    head = content[:2000].lstrip().lower()
    if head.startswith(b"<!doctype html") or b"<html" in head:
        return "html"
    return "unknown"


def fetch_url(
    url: str, timeout: int | None = None, num_retries: int = DEFAULT_NUM_RETRIES
) -> tuple[bytes, SniffedContentType] | None:
    """Returns (content_bytes, sniffed_content_type), or None if the guardrail
    rejects the URL, every retry is exhausted, or the content-type can't be sniffed.
    Never raises — a single unreachable annexure must not fail the whole ingestion
    task (same graceful-degradation contract as _run_pq_checklist/_run_tq_scoring).
    """
    if not is_fetchable_url(url):
        return None

    effective_timeout = (
        timeout if timeout is not None else settings.linked_doc_fetch_timeout_seconds
    )
    last_error: Exception | None = None
    for attempt in range(num_retries + 1):
        try:
            response = requests.get(url, timeout=effective_timeout)
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}")
            response.raise_for_status()
            content_type = _sniff_content_type(response.content)
            if content_type == "unknown":
                logger.warning("fetch_links.unrecognized_content_type", url=url)
                return None
            return response.content, content_type
        except requests.RequestException as exc:
            last_error = exc
            if attempt < num_retries:
                backoff = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "fetch_links.retry",
                    url=url,
                    attempt=attempt + 1,
                    backoff_seconds=round(backoff, 2),
                    error=str(exc),
                )
                time.sleep(backoff)

    logger.warning("fetch_links.fetch_failed_after_retries", url=url, error=str(last_error))
    return None


# --- content-type-specific extraction (HTML / docx only — PDF is handled by the
# caller, reusing app.pipeline.classify/extract_native/extract_vision unchanged) -----


def _extract_html_content(html_bytes: bytes) -> str | None:
    """Isolates real page text from GeM portal chrome — a naive tag-strip on a real
    sample pulled in ~30KB of nav/JS boilerplate around a few KB of actual SLA clause
    text. BeautifulSoup's default parser (stdlib html.parser, no lxml dependency
    needed) plus dropping <script>/<style>/<nav>/<header>/<footer> before extracting
    text is enough to get much closer to the real content.
    """
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return normalized or None


def _extract_docx_content(docx_bytes: bytes) -> str | None:
    doc = DocxDocument(BytesIO(docx_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    text = "\n".join(paragraphs)
    return text or None


def _content_hash(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def resolve_linked_document(url: str) -> LinkedDocumentContent | None:
    """Fetches `url` and routes by its real (sniffed) content type. Returns None on
    any failure — logged inside fetch_url/here, never raised, so one bad link never
    blocks the rest of ingestion.
    """
    fetched = fetch_url(url)
    if fetched is None:
        return None
    content_bytes, content_type = fetched

    if content_type == "pdf":
        return LinkedDocumentContent(source_url=url, kind="pdf", pdf_bytes=content_bytes)

    if content_type == "html":
        text = _extract_html_content(content_bytes)
        return LinkedDocumentContent(source_url=url, kind="text", plain_text=text)

    if content_type == "docx":
        text = _extract_docx_content(content_bytes)
        return LinkedDocumentContent(source_url=url, kind="text", plain_text=text)

    return None  # pragma: no cover - fetch_url already filters "unknown" out


def text_to_page_record(text: str | None) -> PageExtractionResult:
    """Wraps a single extracted HTML/docx string as one synthetic page — HTML/docx
    have no page concept, so the whole linked document becomes exactly one page.
    """
    if not text:
        return PageExtractionResult(
            page_number=0,
            classification="native_text",
            extraction_method="native",
            raw_text=None,
            content_hash=None,
            confidence_score=0.0,
        )
    return PageExtractionResult(
        page_number=0,
        classification="native_text",
        extraction_method="native",
        raw_text=text,
        content_hash=_content_hash(text),
        confidence_score=1.0,
    )


# --- URL-keyed cache (distinct from app.pipeline.dedupe's content_hash-keyed one) ---


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def get_cached_pages(db: Session, url: str) -> list[PageExtractionResult] | None:
    """Returns the cached per-page extraction for `url` if it's been fetched before
    (incrementing hit_count), else None. Mirrors app.pipeline.dedupe.check_and_record's
    db.get(Model, pk) lookup pattern, keyed on a URL hash instead of a content hash.
    """
    existing = db.get(LinkedDocumentCache, _url_hash(url))
    if existing is None or not existing.cached_extraction:
        return None
    existing.hit_count += 1
    existing.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return [PageExtractionResult.model_validate(record) for record in existing.cached_extraction]


def store_cached_pages(
    db: Session, url: str, document_id: uuid.UUID, pages: list[PageExtractionResult]
) -> None:
    row = LinkedDocumentCache(
        url_hash=_url_hash(url),
        source_url=url,
        cached_extraction=[p.model_dump(mode="json") for p in pages],
        first_seen_document_id=document_id,
        hit_count=0,
    )
    db.add(row)
    db.commit()


def is_boilerplate(url: str) -> bool:
    return classify_link(url) == "boilerplate"
