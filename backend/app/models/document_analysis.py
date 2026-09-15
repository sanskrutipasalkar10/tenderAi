import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base

ANALYSIS_MODULES = ("go_no_go", "synopsis", "risk_finder")


class DocumentAnalysis(Base):
    __tablename__ = "document_analysis"
    __table_args__ = (
        CheckConstraint(f"module IN {ANALYSIS_MODULES}", name="document_analysis_module_check"),
        UniqueConstraint("document_id", "module", name="document_analysis_document_id_module_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_used: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
