"""Celery task wrappers around app.pipeline.reduce_pass — one task PER MODULE, not one
task per document, mirroring Phase 4's per-chunk-not-per-document split (tasks_map.py):
a failure in one module (e.g. go_no_go) must not block the other two from completing.
Thin, per CLAUDE.md style; the actual reduce-pass logic lives in the pipeline layer so
it's testable without a broker.
"""

import uuid

from app.storage.db import SessionLocal
from app.workers.celery_app import celery_app


@celery_app.task(name="run_go_no_go_for_document", bind=True, max_retries=3, default_retry_delay=30)
def go_no_go_task(self, document_id: str) -> str:
    from app.models.company_profile import CompanyProfile
    from app.models.document import Document
    from app.pipeline.reduce_pass import run_go_no_go

    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        profile = (
            db.get(CompanyProfile, document.company_profile_id)
            if document.company_profile_id
            else None
        )
        profile_dict = _profile_to_dict(profile)
        analysis = run_go_no_go(db, document, profile_dict)
        return str(analysis.id)
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


@celery_app.task(name="run_synopsis_for_document", bind=True, max_retries=3, default_retry_delay=30)
def synopsis_task(self, document_id: str) -> str:
    from app.models.document import Document
    from app.pipeline.reduce_pass import run_synopsis

    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        analysis = run_synopsis(db, document)
        return str(analysis.id)
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


@celery_app.task(
    name="run_risk_finder_for_document", bind=True, max_retries=3, default_retry_delay=30
)
def risk_finder_task(self, document_id: str) -> str:
    from app.models.document import Document
    from app.pipeline.reduce_pass import run_risk_finder

    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        analysis = run_risk_finder(db, document)
        return str(analysis.id)
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


def _profile_to_dict(profile) -> dict:
    if profile is None:
        return {}
    return {
        "company_name": profile.company_name,
        "annual_turnover": profile.annual_turnover,
        "certifications": profile.certifications,
        "past_projects": profile.past_projects,
        "geographic_presence": profile.geographic_presence,
        "sectors": profile.sectors,
        "max_capacity_pct": profile.max_capacity_pct,
    }
