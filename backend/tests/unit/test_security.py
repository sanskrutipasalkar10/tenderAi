"""Unit tests for app.core.security — no real DB/LLM/network, per CLAUDE.md hard rule 8."""

import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_round_trips_with_verify_password() -> None:
    hashed = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_hash_password_produces_a_different_hash_each_time() -> None:
    # bcrypt salts randomly — two hashes of the same password should differ, but both
    # must still verify.
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")

    assert h1 != h2
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_create_and_decode_access_token_round_trips() -> None:
    token = create_access_token(subject="admin")

    assert decode_access_token(token) == "admin"


def test_decode_access_token_rejects_a_garbage_token() -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token("this-is-not-a-jwt")


def test_decode_access_token_rejects_a_token_signed_with_a_different_secret() -> None:
    from jose import jwt

    forged = jwt.encode({"sub": "admin"}, "a-completely-different-secret", algorithm="HS256")

    with pytest.raises(AuthenticationError):
        decode_access_token(forged)


def test_decode_access_token_rejects_an_expired_token() -> None:
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    from app.core.config import settings

    expired_payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(
        expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(expired_token)
