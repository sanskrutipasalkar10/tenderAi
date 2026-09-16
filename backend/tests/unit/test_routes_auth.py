"""Route-level tests for POST /token — the single shared-credential login
(docs/DECISIONS.md #44). Fakes the Redis rate limiter (no real Redis, hard rule 8).
"""

import pytest
from fastapi.testclient import TestClient

from app.cache import redis_cache
from app.core.config import settings
from app.core.security import decode_access_token
from app.main import app

client = TestClient(app)


class _FakeRedisClient:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key: str, seconds: int) -> None:
        pass


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch):
    monkeypatch.setattr(redis_cache, "_client", _FakeRedisClient())


def test_login_with_correct_credentials_returns_a_usable_token() -> None:
    response = client.post(
        "/token",
        data={
            "username": settings.auth_username,
            "password": "change-me-in-every-environment",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == settings.auth_username


def test_login_with_wrong_password_is_rejected() -> None:
    response = client.post("/token", data={"username": settings.auth_username, "password": "wrong"})

    assert response.status_code == 401


def test_login_with_unknown_username_is_rejected() -> None:
    response = client.post(
        "/token", data={"username": "not-the-shared-user", "password": "anything"}
    )

    assert response.status_code == 401


def test_login_is_rate_limited_after_repeated_failures() -> None:
    for _ in range(settings.login_rate_limit_attempts):
        client.post("/token", data={"username": "rate-limit-probe", "password": "wrong"})

    response = client.post("/token", data={"username": "rate-limit-probe", "password": "wrong"})

    assert response.status_code == 429
