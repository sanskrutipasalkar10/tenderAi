"""POST /token — issues a JWT for the single shared credential (docs/DECISIONS.md
#44). Rate-limited per attempted username (CLAUDE.md hard rule 10) so repeated wrong
guesses can't be brute-forced without bound.
"""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.cache import redis_cache
from app.core import security
from app.core.config import settings
from app.core.exceptions import AuthenticationError

router = APIRouter(tags=["auth"])


@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    redis_cache.check_and_increment(
        f"login_attempts:{form_data.username}",
        limit=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )

    valid_username = form_data.username == settings.auth_username
    valid_password = valid_username and security.verify_password(
        form_data.password, settings.auth_password_hash
    )
    if not valid_password:
        raise AuthenticationError("Incorrect username or password")

    token = security.create_access_token(subject=form_data.username)
    return {"access_token": token, "token_type": "bearer"}
