"""Unit tests for scripts.seed_company_profile — no real DB, per CLAUDE.md hard rule 8."""

import uuid

import pytest

from app.models.company_profile import CompanyProfile
from scripts.seed_company_profile import upsert_profile


class _FakeQuery:
    def __init__(self, result: CompanyProfile | None) -> None:
        self._result = result

    def filter(self, *_conditions):
        return self

    def first(self):
        return self._result


class _FakeSession:
    def __init__(self, existing: CompanyProfile | None = None) -> None:
        self._existing = existing
        self.added: list = []

    def query(self, model):
        assert model is CompanyProfile
        return _FakeQuery(self._existing)

    def add(self, obj) -> None:
        obj.id = obj.id or uuid.uuid4()
        self.added.append(obj)

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        pass


def test_upsert_creates_a_new_profile_when_none_exists() -> None:
    db = _FakeSession(existing=None)
    payload = {"company_name": "Acme Infra", "max_capacity_pct": 60}

    profile = upsert_profile(db, payload)

    assert profile.company_name == "Acme Infra"
    assert profile.max_capacity_pct == 60
    assert profile in db.added


def test_upsert_updates_the_existing_profile_in_place_not_a_duplicate() -> None:
    existing = CompanyProfile(id=uuid.uuid4(), company_name="Acme Infra", max_capacity_pct=50)
    db = _FakeSession(existing=existing)
    payload = {"company_name": "Acme Infra", "max_capacity_pct": 70, "sectors": ["roads"]}

    profile = upsert_profile(db, payload)

    assert profile is existing
    assert profile.max_capacity_pct == 70
    assert profile.sectors == ["roads"]
    assert db.added == []  # nothing new added — same row updated


def test_unknown_field_in_payload_is_rejected() -> None:
    db = _FakeSession()
    payload = {"company_name": "Acme Infra", "gstin": "27AAAAA0000A1Z5"}

    with pytest.raises(ValueError, match="not in company_profiles"):
        upsert_profile(db, payload)


def test_omitted_fields_are_left_untouched_on_update() -> None:
    existing = CompanyProfile(
        id=uuid.uuid4(), company_name="Acme Infra", sectors=["roads"], max_capacity_pct=50
    )
    db = _FakeSession(existing=existing)
    payload = {"company_name": "Acme Infra", "max_capacity_pct": 55}  # sectors omitted

    profile = upsert_profile(db, payload)

    assert profile.sectors == ["roads"]  # untouched, not wiped to null
    assert profile.max_capacity_pct == 55
