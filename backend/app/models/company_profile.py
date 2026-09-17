import uuid
from datetime import datetime

from sqlalchemy import JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    annual_turnover: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    certifications: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    past_projects: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    geographic_presence: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite")
    )
    sectors: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    max_capacity_pct: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    # onupdate is an ORM-level behavior (touches the column on every SQLAlchemy
    # UPDATE), not a schema change — the column itself is exactly the DDL's, applied
    # verbatim. Without this, routes_company_profiles.py's PUT endpoint would leave
    # updated_at silently stale forever.
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
