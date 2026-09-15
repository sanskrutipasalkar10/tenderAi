from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class BoilerplateCache(Base):
    __tablename__ = "boilerplate_cache"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    issuing_authority: Mapped[str | None] = mapped_column(Text)
    cached_extraction: Mapped[dict | None] = mapped_column(JSONB)
    first_seen_document_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
