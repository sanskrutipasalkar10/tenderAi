import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base

PAGE_CLASSIFICATIONS = ("native_text", "scanned_image", "table", "mixed")
EXTRACTION_METHODS = ("native", "vision_cloud", "vision_local")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        CheckConstraint(
            f"classification IN {PAGE_CLASSIFICATIONS}", name="pages_classification_check"
        ),
        CheckConstraint(
            f"extraction_method IN {EXTRACTION_METHODS}", name="pages_extraction_method_check"
        ),
        UniqueConstraint(
            "document_id", "page_number", name="pages_document_id_page_number_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    classification: Mapped[str] = mapped_column(String, nullable=False)
    extraction_method: Mapped[str | None] = mapped_column(String)
    raw_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    image_s3_key: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
