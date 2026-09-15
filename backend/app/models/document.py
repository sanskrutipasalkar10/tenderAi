import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base

DOCUMENT_STATUSES = (
    "uploaded",
    "classifying",
    "extracting",
    "extracted",
    "analyzing",
    "ready",
    "failed",
)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"status IN {DOCUMENT_STATUSES}", name="documents_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    issuing_authority: Mapped[str | None] = mapped_column(Text)
    total_pages: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="uploaded")
    original_pdf_s3_key: Mapped[str | None] = mapped_column(Text)
    company_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_profiles.id")
    )
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
