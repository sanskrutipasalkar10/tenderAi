"""Extends company_profiles with real statutory/financial fields sourced from
docs/sutf-company-profile-decision-grade.docx (C4i4/SUTF's actual, decision-grade
company profile) — CIN, PAN, GSTIN, Udyam/MSME registration, directors, bank
details, employment, government grants, and net worth. All nullable: most start
unknown and get filled in over time, per the same "seed now with nulls, complete
later" approach as the original company_profiles seed (docs/DECISIONS.md #51).

`turnover_source` is the load-bearing addition here — the direct fix for a real
problem the docx found: two turnover figures on file for the same company with no
record of which was actually confirmed against this legal entity's PAN/CIN. Every
write to `annual_turnover` must now also set `turnover_source` (enforced at the
application layer, in app.models.schemas.CompanyProfileWrite, not here — a DB-level
CHECK spanning two nullable JSONB/TEXT columns isn't worth the complexity for a
single-writer internal tool). `unconfirmed_org_turnover_inr` holds the figure that
should NOT be used for scoring until its entity attribution is confirmed by a human
— retained, never deleted, per this project's "never lose a source figure, flag it
instead" principle (see docs/DECISIONS.md's own past entries on this theme).

See docs/DECISIONS.md for the full row on this change, including why this migration
does NOT also add pq_criteria/tq_criteria/bid_decision_factors/hard_fail_gates
reference tables (a deliberate, scoped-down deviation from
docs/pq-tq-framework-implementation-plan.md's Section 1 — those are Phase 2 concerns
this migration doesn't need).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DDL = """
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS cin TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS roc_number TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS section8_licence_number TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS date_of_incorporation DATE;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS pan TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS gstin TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS udyam_registration_number TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS msme_classification JSONB;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS ngo_darpan_id TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS authorised_capital_inr NUMERIC;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS paid_up_capital_inr NUMERIC;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS net_worth_inr NUMERIC;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS turnover_source TEXT;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS unconfirmed_org_turnover_inr JSONB;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS directors JSONB;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS bank_details JSONB;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS employment_count JSONB;
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS government_grants JSONB;
"""

DROP_ALL = """
ALTER TABLE company_profiles DROP COLUMN IF EXISTS cin;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS roc_number;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS section8_licence_number;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS date_of_incorporation;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS pan;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS gstin;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS udyam_registration_number;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS msme_classification;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS ngo_darpan_id;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS authorised_capital_inr;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS paid_up_capital_inr;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS net_worth_inr;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS turnover_source;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS unconfirmed_org_turnover_inr;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS directors;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS bank_details;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS employment_count;
ALTER TABLE company_profiles DROP COLUMN IF EXISTS government_grants;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP_ALL)
