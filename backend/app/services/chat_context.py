"""Builds the chat assistant's document-grounding context from already-computed
document_analysis rows (synopsis/go_no_go/risk_finder) — no retrieval step and no new
extraction, consistent with this project's pipeline-not-agent architecture (CLAUDE.md).
If a document hasn't been analyzed yet, there's simply nothing to ground on for that
turn; the assistant falls back to answering from general knowledge.
"""

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.analysis_reader import get_all_analysis


def build_document_context(db: Session, document_id: UUID) -> str | None:
    analyses = get_all_analysis(db, document_id)
    if not analyses:
        return None
    return "\n\n".join(
        f"[{analysis.module}]\n{json.dumps(analysis.result, indent=2, default=str)}"
        for analysis in analyses
    )
