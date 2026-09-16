"""JWT creation/verification and password hashing — the only file that touches either.
Auth is a single shared credential, not per-user (docs/DECISIONS.md #44): the spec's
own DDL has no users table, so `create_access_token`'s subject is always
`settings.auth_username`, never a database-backed user id.

Uses `bcrypt` directly, not `passlib[bcrypt]` (docs/DECISIONS.md #43) — passlib 1.7.4's
bcrypt backend crashes at import time against the bcrypt version this project actually
resolves to.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_password(plain_password: str) -> str:
    """Not called at runtime (the one credential's hash lives in config) — exists so a
    new deployment can generate `AUTH_PASSWORD_HASH` for its `.env` without needing a
    separate script: `python -c "from app.core.security import hash_password as h;
    print(h('new-password'))"`.
    """
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Returns the token's subject (the shared username) or raises AuthenticationError
    — never lets a raw JWTError (expired, malformed, wrong signature) reach a route.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise AuthenticationError("Invalid token payload")
    return subject
