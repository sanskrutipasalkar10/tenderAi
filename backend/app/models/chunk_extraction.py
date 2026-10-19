import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class ChunkExtraction(Base):
    __tablename__ = "chunk_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    structured_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_used: Mapped[str | None] = mapped_column(Text)
    # Set only when this row was synthesized from a ChunkExtractionCache hit rather
    # than a fresh LLM call (migration 0008) — points at the chunk whose original
    # extraction produced the cached entry. NULL for the common, genuinely-fresh case.
    reused_from_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
