"""CRUD for company_profiles — the reduce pass's go_no_go input (docs/DECISIONS.md
#59). Until now the only way to create one was `scripts/seed_company_profile.py`
(docs/DECISIONS.md #51); this is what the frontend's company-profile page calls.

Deliberately thin: no required-fields validation here (that's app.pipeline.
reduce_pass.REQUIRED_PROFILE_FIELDS, checked at analysis time, not save time) — an
incomplete profile is a valid, normal thing to save and come back to later.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.company_profile import CompanyProfile
from app.models.schemas import CompanyProfileResponse, CompanyProfileWrite

router = APIRouter(prefix="/company-profiles", tags=["company-profiles"])


@router.post("", response_model=CompanyProfileResponse, status_code=201)
def create_company_profile(
    payload: CompanyProfileWrite, db: Session = Depends(get_db)
) -> CompanyProfile:
    profile = CompanyProfile(**payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=list[CompanyProfileResponse])
def list_company_profiles(db: Session = Depends(get_db)) -> list[CompanyProfile]:
    return list(db.query(CompanyProfile).order_by(CompanyProfile.company_name).all())


@router.get("/{profile_id}", response_model=CompanyProfileResponse)
def get_company_profile(profile_id: uuid.UUID, db: Session = Depends(get_db)) -> CompanyProfile:
    profile = db.get(CompanyProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No such company profile")
    return profile


@router.put("/{profile_id}", response_model=CompanyProfileResponse)
def update_company_profile(
    profile_id: uuid.UUID, payload: CompanyProfileWrite, db: Session = Depends(get_db)
) -> CompanyProfile:
    profile = db.get(CompanyProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No such company profile")
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
