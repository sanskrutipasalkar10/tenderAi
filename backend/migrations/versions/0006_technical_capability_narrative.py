"""Adds company_profiles.technical_capability_narrative — a free-text knowledge base,
one entry per TQ scoring factor (app.pipeline.reduce_pass.TQ_FACTOR_WEIGHTS), used by
the TQ-scoring prompt (v1_tq_scoring.md) as primary evidence for the 7 factors that ask
about a proposed technical response rather than a static company attribute (Technical
Solution/Methodology, Proposed Architecture/Solution Design, Key Personnel,
Implementation Methodology, Project Management Approach, Support/O&M Approach,
Innovation/Value Addition).

Deliberately NOT reused from an existing JSONB column (employment_count/past_projects
already each hold one unrelated note from earlier updates) — this is a large, distinct,
reused-on-every-tender knowledge base, not a one-off annotation, and piling a second
unrelated blob onto an existing column would make it progressively harder for anyone
else to find. A real, named column is the honest home for it.

Deliberately excludes "Understanding of Requirements" (one of the 8 proposal-shaped TQ
factors) — the user who provided this content was explicit that this one is genuinely
tender-specific and can't be meaningfully pre-answered from a company profile; the
prompt already handles it by inferring from sector/domain overlap instead, no
knowledge-base entry needed or wanted for it.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DDL = """
ALTER TABLE company_profiles ADD COLUMN IF NOT EXISTS technical_capability_narrative JSONB;
"""

DROP_ALL = """
ALTER TABLE company_profiles DROP COLUMN IF EXISTS technical_capability_narrative;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP_ALL)
