"""Citation re-verification — the real faithfulness metric for this project (no
retrieval step to measure recall/faithfulness against, see docs/DECISIONS.md #4).
Re-checked here, independently of whatever a reduce-pass model claims, because a
`page_ref` is only trustworthy if it resolves to a real page that was actually part of
this document (docs/SPEC.md §8's own success criterion).

Runs after every reduce-pass module call, before its result is persisted — never trust
a model's citation at face value (CLAUDE.md hard rule 6).
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.page import Page

logger = get_logger(__name__)


def page_ref_resolves(db: Session, document_id, page_ref: int) -> bool:
    """A page_ref is verifiable only if a `pages` row exists for this exact
    (document_id, page_number) — the spec's own definition of "verifiable"
    (docs/SPEC.md §8: "100% of page_refs resolve to an existing pages row").
    """
    return (
        db.query(Page)
        .filter(Page.document_id == document_id, Page.page_number == page_ref)
        .first()
        is not None
    )


def verify_risk_citations(db: Session, document_id, risks: list[dict]) -> list[dict]:
    """Sets `verified` on each risk in place from a real DB check, overriding
    whatever the model may have claimed (models never self-certify their own
    citations). An unresolvable page_ref is never dropped — per docs/SPEC.md §7, an
    unverified fact is shown as unverified, never hidden or guessed away.
    """
    verified_risks = []
    for risk in risks:
        resolves = page_ref_resolves(db, document_id, risk["page_ref"])
        if not resolves:
            logger.warning(
                "citation_verify.unresolvable_page_ref",
                document_id=str(document_id),
                page_ref=risk["page_ref"],
                category=risk.get("category"),
            )
        verified_risks.append({**risk, "verified": resolves})
    return verified_risks
