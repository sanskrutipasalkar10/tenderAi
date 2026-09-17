"""Upserts a company_profiles row from a JSON payload matching the table's real
columns (company_name, annual_turnover, certifications, past_projects,
geographic_presence, sectors, max_capacity_pct — docs/SPEC.md §3.1's DDL, applied
verbatim, no extra fields). Run: `python scripts/seed_company_profile.py
scripts/seed_data/<file>.json` from `backend/`, with the venv active and
DATABASE_URL pointing at a real Postgres.

Upserts by exact `company_name` match (the DDL has no UNIQUE constraint on it, so this
is a scripted convention, not a DB-enforced one) — re-running with an updated JSON
file for the same company_name replaces the row rather than creating a duplicate, so a
profile that's explicitly a work in progress (docs/DECISIONS.md #51) can be re-seeded
as fields get filled in.
"""

import json
import sys
from pathlib import Path

from app.models.company_profile import CompanyProfile
from app.storage.db import SessionLocal

PROFILE_FIELDS = (
    "company_name",
    "annual_turnover",
    "certifications",
    "past_projects",
    "geographic_presence",
    "sectors",
    "max_capacity_pct",
)


def upsert_profile(db, payload: dict) -> CompanyProfile:
    unknown_fields = set(payload) - set(PROFILE_FIELDS)
    if unknown_fields:
        raise ValueError(
            f"Payload has fields not in company_profiles' real schema: {unknown_fields}. "
            "The DDL is applied as-is (CLAUDE.md) — a field belongs elsewhere, not here."
        )

    existing = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.company_name == payload["company_name"])
        .first()
    )
    profile = existing or CompanyProfile(company_name=payload["company_name"])
    for field in PROFILE_FIELDS:
        if field in payload:
            setattr(profile, field, payload[field])

    if existing is None:
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/seed_company_profile.py <path-to-profile.json>")
        sys.exit(1)

    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        profile = upsert_profile(db, payload)
        print(
            f"Upserted company_profiles row: id={profile.id} "
            f"company_name={profile.company_name!r}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
