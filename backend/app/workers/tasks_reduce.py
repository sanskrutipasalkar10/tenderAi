"""Celery task wrappers around app.pipeline.reduce_pass — one task PER MODULE, not one
task per document, mirroring Phase 4's per-chunk-not-per-document split (tasks_map.py):
a failure in one module (e.g. go_no_go) must not block the other two from completing.
Thin, per CLAUDE.md style; the actual reduce-pass logic lives in the pipeline layer so
it's testable without a broker.

Runs on the "llm" queue with the same time limit as tasks_map.py (docs/DECISIONS.md
#47) — reduce calls are real Ollama calls too, though real Phase 5 validation showed
them consistently faster (~5-8s) than map-pass calls, since they process aggregated
facts rather than full page text.
"""

import uuid

from app.core.logging import get_logger
from app.storage.db import SessionLocal
from app.workers.celery_app import LLM_TASK_SOFT_TIME_LIMIT, LLM_TASK_TIME_LIMIT, celery_app

logger = get_logger(__name__)

_TASK_KWARGS = {
    "bind": True,
    "max_retries": 3,
    "default_retry_delay": 30,
    "queue": "llm",
    "soft_time_limit": LLM_TASK_SOFT_TIME_LIMIT,
    "time_limit": LLM_TASK_TIME_LIMIT,
}


def _retry_or_give_up(self, exc: Exception, module: str, document_id: str) -> None:
    """Shared by all three module tasks below — same reasoning as
    tasks_map.py's map_pass_chunk_task (docs/DECISIONS.md #62): these three tasks are
    the header of a Celery chord (tasks_pipeline.py's _start_reduce_pass), and one
    permanently-failed module must not block mark_document_ready from ever firing for
    the other two, which may well have succeeded.
    """
    if self.request.retries < self.max_retries:
        raise self.retry(exc=exc) from exc
    logger.error(
        f"reduce_pass.{module}_permanently_failed", document_id=document_id, error=str(exc)
    )


@celery_app.task(name="run_go_no_go_for_document", **_TASK_KWARGS)
def go_no_go_task(self, document_id: str) -> str | None:
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
        profile_dict = profile_to_dict(profile)
        analysis = run_go_no_go(db, document, profile_dict)
        return str(analysis.id)
    except Exception as exc:  # noqa: BLE001 - Celery's own retry mechanism needs the broad catch
        db.rollback()
        _retry_or_give_up(self, exc, "go_no_go", document_id)
        return None
    finally:
        db.close()


@celery_app.task(name="run_synopsis_for_document", **_TASK_KWARGS)
def synopsis_task(self, document_id: str) -> str | None:
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
        _retry_or_give_up(self, exc, "synopsis", document_id)
        return None
    finally:
        db.close()


@celery_app.task(name="run_risk_finder_for_document", **_TASK_KWARGS)
def risk_finder_task(self, document_id: str) -> str | None:
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
        _retry_or_give_up(self, exc, "risk_finder", document_id)
        return None
    finally:
        db.close()


def profile_to_dict(profile) -> dict:
    """Every company_profile field the tender might ask about — docs/DECISIONS.md
    (#65 follow-up): the real PQ checklist (docs/C4i4_Tender_PQ_TQ_BID_NO_BID_
    Framework.xlsx, Section A rows 3-4) lists PAN and GST registration as real PQ
    criteria, so a tender criterion asking for either was being marked "no
    information provided" -> FAIL purely because the field was withheld from the
    model, not because the company actually lacks it. Widening this was a deliberate
    user request, not a default worth reverting to without asking.

    No longer module-private — reused by routes_analysis.py's resubmit-rescoring
    endpoint (docs/DECISIONS.md), which needs the exact same profile subset the
    original go_no_go_task used.

    The one deliberate exception: `unconfirmed_org_turnover_inr` is NEVER sent. That
    field isn't merely out-of-scope like the others were — the source docx (see
    migration 0003) explicitly flags those figures as unconfirmed against this legal
    entity's PAN/CIN. Sending it risks the model scoring Financial Capability off
    numbers we already know might be wrong. Excluding it here (never exposing it) is
    still the only way to guarantee it can't be used, per the same reasoning as
    before.
    """
    if profile is None:
        return {}
    return {
        "company_name": profile.company_name,
        "annual_turnover": profile.annual_turnover,
        "turnover_source": profile.turnover_source,
        "certifications": profile.certifications,
        "past_projects": profile.past_projects,
        "geographic_presence": profile.geographic_presence,
        "sectors": profile.sectors,
        "max_capacity_pct": profile.max_capacity_pct,
        "cin": profile.cin,
        "roc_number": profile.roc_number,
        "section8_licence_number": profile.section8_licence_number,
        "date_of_incorporation": (
            profile.date_of_incorporation.isoformat() if profile.date_of_incorporation else None
        ),
        "pan": profile.pan,
        "gstin": profile.gstin,
        "udyam_registration_number": profile.udyam_registration_number,
        "msme_classification": profile.msme_classification,
        "ngo_darpan_id": profile.ngo_darpan_id,
        "authorised_capital_inr": profile.authorised_capital_inr,
        "paid_up_capital_inr": profile.paid_up_capital_inr,
        "net_worth_inr": profile.net_worth_inr,
        "directors": profile.directors,
        "bank_details": profile.bank_details,
        "employment_count": profile.employment_count,
        "government_grants": profile.government_grants,
        # unconfirmed_org_turnover_inr: deliberately excluded, see docstring above.
    }
