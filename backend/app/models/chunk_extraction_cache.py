import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class ChunkExtractionCache(Base):
    """Content-hash keyed reuse of a map-pass extraction — mirrors BoilerplateCache's
    and LinkedDocumentCache's shape (migration 0008, docs/DECISIONS.md #75's "a new
    table per distinct identity" reasoning: this one's key means "seen this exact
    chunk's content, here's its structured extraction," different from either of
    those). See app.pipeline.map_pass_cache for how this is read/written.
    """

    __tablename__ = "chunk_extraction_cache"

    content_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    cached_structured_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Ordered page_number list the cached extraction's page_refs were originally
    # computed against — required to remap them onto a reusing chunk's real pages.
    cached_original_pages: Mapped[list] = mapped_column(JSONB, nullable=False)
    cached_model_used: Mapped[str | None] = mapped_column(Text)
    first_seen_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id")
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
