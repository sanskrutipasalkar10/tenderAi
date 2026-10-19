"""Adds documents.failure_reason — set only on the terminal status="failed"
transition, surfacing why the pipeline stopped (e.g. "Ingestion failed after 3
retries: <error>") directly to the frontend instead of requiring a dig through
worker logs for every stuck/failed document.

Companion fix, same root cause investigation, no schema change needed for it:
documents.updated_at previously had no `onupdate`, so it was insert-only in
practice — useless as a "last activity" signal. That's an app.models.document.py
ORM-level fix (onupdate=func.now()), not a DDL change, so it isn't in this migration.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DDL = """
ALTER TABLE documents ADD COLUMN IF NOT EXISTS failure_reason TEXT;
"""

DROP_ALL = """
ALTER TABLE documents DROP COLUMN IF EXISTS failure_reason;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DROP_ALL)
