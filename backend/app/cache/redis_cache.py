"""Redis-backed rate limiting — currently just the login endpoint's brute-force guard
(CLAUDE.md hard rule 10: every external-facing endpoint needs an explicit
too-many-attempts path, not just the LLM/S3 calls). A fixed-window counter, not a
sliding-window/token-bucket algorithm — simple, and login attempts are rare enough that
window-edge burstiness isn't a real concern here.

`_client` is module-level and swappable (tests monkeypatch it with a fake) rather than
constructed inside `check_and_increment` — this module never needs a real Redis in
tests, per CLAUDE.md hard rule 8.
"""

import redis

from app.core.config import settings
from app.core.exceptions import RateLimitError

_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)


def check_and_increment(key: str, *, limit: int, window_seconds: int) -> None:
    """Raises RateLimitError if `key` has already been incremented `limit` times
    within the current `window_seconds` window; otherwise increments and returns.
    """
    count = _client.incr(key)
    if count == 1:
        _client.expire(key, window_seconds)
    if count > limit:
        raise RateLimitError("Too many attempts — try again in a few minutes")
