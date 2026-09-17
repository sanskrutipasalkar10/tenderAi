"""Route-level tests for company_profiles CRUD — the only way to manage a profile
before this was scripts/seed_company_profile.py (docs/DECISIONS.md #51/#59).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.company_profile import CompanyProfile

client = TestClient(app)


def _fake_refresh(obj) -> None:
    if getattr(obj, "id", None) is None:
        obj.id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    if getattr(obj, "created_at", None) is None:
        obj.created_at = now
    if getattr(obj, "updated_at", None) is None:
        obj.updated_at = now


@pytest.fixture(autouse=True)
def _overrides():
    fake_db = MagicMock()
    fake_db.refresh.side_effect = _fake_refresh
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    yield fake_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_create_company_profile(_overrides) -> None:
    response = client.post(
        "/company-profiles",
        json={
            "company_name": "Acme Infra",
            "annual_turnover": {"2024": 50000000},
            "certifications": ["ISO 9001:2015"],
            "sectors": ["roads"],
            "max_capacity_pct": 60,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["company_name"] == "Acme Infra"
    assert body["sectors"] == ["roads"]
    _overrides.add.assert_called_once()


def test_create_company_profile_allows_an_incomplete_profile(_overrides) -> None:
    # Deliberately no required-fields validation at save time (routes_company_profiles
    # .py's own docstring) — that check belongs to reduce_pass.py, at analysis time.
    response = client.post("/company-profiles", json={"company_name": "Work In Progress"})

    assert response.status_code == 201
    assert response.json()["certifications"] is None


def test_list_company_profiles(_overrides) -> None:
    now = datetime.now(timezone.utc)
    profile = CompanyProfile(
        id=uuid.uuid4(), company_name="Acme Infra", created_at=now, updated_at=now
    )
    _overrides.query.return_value.order_by.return_value.all.return_value = [profile]

    response = client.get("/company-profiles")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_company_profile_404s_when_missing(_overrides) -> None:
    _overrides.get.return_value = None

    response = client.get(f"/company-profiles/{uuid.uuid4()}")

    assert response.status_code == 404


def test_update_company_profile(_overrides) -> None:
    profile = CompanyProfile(id=uuid.uuid4(), company_name="Old Name", max_capacity_pct=50)
    _overrides.get.return_value = profile

    response = client.put(
        f"/company-profiles/{profile.id}",
        json={"company_name": "New Name", "max_capacity_pct": 75},
    )

    assert response.status_code == 200
    assert response.json()["company_name"] == "New Name"
    assert response.json()["max_capacity_pct"] == 75


def test_update_company_profile_404s_when_missing(_overrides) -> None:
    _overrides.get.return_value = None

    response = client.put(f"/company-profiles/{uuid.uuid4()}", json={"company_name": "X"})

    assert response.status_code == 404


def test_company_profile_routes_require_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.get("/company-profiles")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: "test-user"
