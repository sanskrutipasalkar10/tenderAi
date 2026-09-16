from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core import security
from app.storage.db import get_db

__all__ = ["get_current_user", "get_db"]

# tokenUrl is only used to populate OpenAPI's "Authorize" flow — the actual login
# route lives in app.api.routes_auth.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Returns the shared username from a valid JWT, or raises AuthenticationError
    (401) via app.core.security.decode_access_token — there's no per-user identity to
    look up (docs/DECISIONS.md #44), so a valid token IS the authenticated principal.
    """
    return security.decode_access_token(token)
