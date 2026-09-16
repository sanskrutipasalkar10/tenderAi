"""ORM models for the Bronze/Silver/Gold export/reporting schema (migration 0002).

This is a DERIVED layer, not the system of record — see docs/DECISIONS.md #17 and
docs/ARCHITECTURE.md's "Bronze/Silver/Gold export layer" section. Grouped in one file
(unlike the one-model-per-file convention elsewhere in this package) because these four
tables represent a single external contract owned by someone else, not our own layered
design — keeping them together makes that boundary obvious.

The sync logic that populates these from our canonical schema is Phase 5+ work.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class CompanyMasterProfile(Base):
    __tablename__ = "company_master_profile"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())


class TenderBronzeRaw(Base):
    __tablename__ = "tender_bronze_raw"

    bronze_chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_master_profile.company_id", ondelete="CASCADE"), nullable=False
    )
    chunk_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    page_range: Mapped[str | None] = mapped_column(String(50))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())


class TenderSilverExtracted(Base):
    __tablename__ = "tender_silver_extracted"

    silver_fact_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[str] = mapped_column(String(255), nullable=False)
    bronze_chunk_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tender_bronze_raw.bronze_chunk_id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_master_profile.company_id", ondelete="CASCADE"), nullable=False
    )
    extracted_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())


class TenderGoldAnalysis(Base):
    __tablename__ = "tender_gold_analysis"
    __table_args__ = (UniqueConstraint("tender_id", name="tender_gold_analysis_tender_id_key"),)

    gold_analysis_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_master_profile.company_id", ondelete="CASCADE"), nullable=False
    )
    go_nogo_status: Mapped[str] = mapped_column(String(50), nullable=False)
    go_nogo_score: Mapped[int | None] = mapped_column(Integer)
    # match_report also carries a nested "synopsis" key — see docs/ARCHITECTURE.md,
    # this schema has no dedicated synopsis column.
    match_report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    document_roadmap: Mapped[dict | None] = mapped_column(JSONB)
    risk_matrix: Mapped[dict | None] = mapped_column(JSONB)
    evaluated_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
