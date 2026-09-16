"""Serving layer for document_analysis — read-only, never recomputes. The
UNIQUE(document_id, module) constraint plus reduce_pass.py's own upsert logic already
guarantee "re-opening an analyzed tender costs zero recomputation" (docs/SPEC.md §8);
this module just reads what's there.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document_analysis import DocumentAnalysis


def get_analysis(db: Session, document_id: UUID, module: str) -> DocumentAnalysis | None:
    return (
        db.query(DocumentAnalysis)
        .filter(DocumentAnalysis.document_id == document_id, DocumentAnalysis.module == module)
        .first()
    )


def get_all_analysis(db: Session, document_id: UUID) -> list[DocumentAnalysis]:
    return (
        db.query(DocumentAnalysis).filter(DocumentAnalysis.document_id == document_id).all()
    )
