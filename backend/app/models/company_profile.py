import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, Numeric, String, Text, func
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

    # Statutory/financial fields (docs/DECISIONS.md's SUTF-profile row; migration
    # 0003) — sourced from docs/sutf-company-profile-decision-grade.docx, all
    # nullable since most start unknown and get filled in over time.
    cin: Mapped[str | None] = mapped_column(Text)
    roc_number: Mapped[str | None] = mapped_column(Text)
    section8_licence_number: Mapped[str | None] = mapped_column(Text)
    date_of_incorporation: Mapped[date | None] = mapped_column(Date)
    pan: Mapped[str | None] = mapped_column(Text)
    gstin: Mapped[str | None] = mapped_column(Text)
    udyam_registration_number: Mapped[str | None] = mapped_column(Text)
    msme_classification: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    ngo_darpan_id: Mapped[str | None] = mapped_column(Text)
    authorised_capital_inr: Mapped[float | None] = mapped_column(Numeric)
    paid_up_capital_inr: Mapped[float | None] = mapped_column(Numeric)
    net_worth_inr: Mapped[float | None] = mapped_column(Numeric)
    # Names which document annual_turnover's figures came from — must be set
    # whenever annual_turnover is (enforced in app.models.schemas.CompanyProfileWrite,
    # not here; see migration 0003's own docstring for why).
    turnover_source: Mapped[str | None] = mapped_column(Text)
    # Retained, never scored against, per the docx's own explicit warning — see
    # migration 0003.
    unconfirmed_org_turnover_inr: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite")
    )
    directors: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    bank_details: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    employment_count: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    government_grants: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    # onupdate is an ORM-level behavior (touches the column on every SQLAlchemy
    # UPDATE), not a schema change — the column itself is exactly the DDL's, applied
    # verbatim. Without this, routes_company_profiles.py's PUT endpoint would leave
    # updated_at silently stale forever.
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
