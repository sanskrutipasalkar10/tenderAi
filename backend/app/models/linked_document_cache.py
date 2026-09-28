from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class LinkedDocumentCache(Base):
    """Caches a fetched-and-extracted hyperlinked document by URL identity — distinct
    from BoilerplateCache (app.models.boilerplate_cache), whose content_hash PK means
    "I've seen this exact extracted text before" (a different identity: content, not
    address). This table means "I've already fetched this URL before," which matters
    for the boilerplate-style GeM links (General Terms & Conditions, "list of
    categories where trials are allowed", etc.) that reuse the same URL across many
    different tenders — see docs/DECISIONS.md.
    """

    __tablename__ = "linked_document_cache"

    url_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(canonical_url)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    # One entry per page the linked document produced: {raw_text, classification,
    # extraction_method, confidence_score} — same shape PageExtractionResult carries,
    # re-hydrated into Page rows on a cache hit without re-fetching or re-extracting.
    cached_extraction: Mapped[list | None] = mapped_column(JSONB)
    first_seen_document_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
