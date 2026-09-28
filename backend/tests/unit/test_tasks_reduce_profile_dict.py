"""profile_to_dict — what subset of company_profiles reaches the go_no_go prompt.
Widened to every field except unconfirmed_org_turnover_inr (user request, following
up on a real gap: PAN/GST are actual PQ criteria per docs/C4i4_Tender_PQ_TQ_BID_NO_BID_
Framework.xlsx Section A, so withholding them caused false FAILs). The one exclusion
stays deliberate and must never regress silently — that's the field this test guards.
"""

import uuid
from datetime import date

# Import order matters here: app.workers.tasks_reduce <-> app.workers.celery_app
# (via tasks_pipeline) is circular. Importing celery_app first, fully, avoids hitting
# tasks_reduce mid-init if this file is collected/run before anything else establishes
# that order — a genuine pre-existing fragility (worth fixing at the source someday),
# not something to silently work around by reordering unrelated test files.
import app.workers.celery_app  # noqa: F401
from app.models.company_profile import CompanyProfile
from app.workers.tasks_reduce import profile_to_dict


def _full_profile() -> CompanyProfile:
    return CompanyProfile(
        id=uuid.uuid4(),
        company_name="Acme Infra",
        annual_turnover={"2024": 50000000},
        turnover_source="audited_financials",
        certifications=["ISO 9001:2015"],
        past_projects=[{"name": "Road works"}],
        geographic_presence=["Maharashtra"],
        sectors=["roads"],
        max_capacity_pct=60,
        cin="U74999PN2017NPL172629",
        roc_number="172629",
        section8_licence_number="110090",
        date_of_incorporation=date(2017, 9, 20),
        pan="AAZCS2482C",
        gstin="27AAZCS2482C1ZX",
        udyam_registration_number="UDYAM-MH-26-0843671",
        msme_classification=[{"year": "2024-25", "type": "Small"}],
        ngo_darpan_id="MH/2018/0190409",
        authorised_capital_inr=300000,
        paid_up_capital_inr=300000,
        net_worth_inr=1000000,
        unconfirmed_org_turnover_inr={"2024": 999999999},
        directors=[{"name": "A Director"}],
        bank_details={"bank": "Axis Bank"},
        employment_count={"male": 10, "female": 5, "other": 0},
        government_grants=[{"department": "MoHI"}],
    )


def test_none_profile_returns_empty_dict() -> None:
    assert profile_to_dict(None) == {}


def test_unconfirmed_org_turnover_is_never_sent() -> None:
    result = profile_to_dict(_full_profile())
    assert "unconfirmed_org_turnover_inr" not in result


def test_every_other_field_is_sent() -> None:
    profile = _full_profile()
    result = profile_to_dict(profile)

    expected_fields = {
        "company_name", "annual_turnover", "turnover_source", "certifications",
        "past_projects", "geographic_presence", "sectors", "max_capacity_pct",
        "cin", "roc_number", "section8_licence_number", "date_of_incorporation",
        "pan", "gstin", "udyam_registration_number", "msme_classification",
        "ngo_darpan_id", "authorised_capital_inr", "paid_up_capital_inr",
        "net_worth_inr", "directors", "bank_details", "employment_count",
        "government_grants",
    }
    assert set(result.keys()) == expected_fields
    assert result["pan"] == "AAZCS2482C"
    assert result["gstin"] == "27AAZCS2482C1ZX"
    assert result["bank_details"] == {"bank": "Axis Bank"}
    assert result["date_of_incorporation"] == "2017-09-20"  # date -> isoformat string


def test_none_date_of_incorporation_stays_none() -> None:
    profile = _full_profile()
    profile.date_of_incorporation = None
    result = profile_to_dict(profile)
    assert result["date_of_incorporation"] is None
