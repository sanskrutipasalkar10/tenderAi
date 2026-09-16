"""Unit tests for app.cache.redis_cache — fakes the Redis client (module-level `_client`
swapped via monkeypatch), no real Redis needed, per CLAUDE.md hard rule 8.
"""

import pytest

from app.cache import redis_cache
from app.core.exceptions import RateLimitError


class FakeRedisClient:
    """Just enough of redis-py's interface for check_and_increment: incr + expire,
    backed by an in-memory dict — no TTL expiry simulation needed since no test here
    waits out a real window.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []

    def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expire_calls.append((key, seconds))


@pytest.fixture(autouse=True)
def _fake_client(monkeypatch):
    fake = FakeRedisClient()
    monkeypatch.setattr(redis_cache, "_client", fake)
    return fake


def test_first_attempt_is_allowed_and_sets_a_ttl(_fake_client) -> None:
    redis_cache.check_and_increment("login:admin", limit=5, window_seconds=300)

    assert _fake_client.expire_calls == [("login:admin", 300)]


def test_attempts_under_the_limit_are_allowed() -> None:
    for _ in range(5):
        redis_cache.check_and_increment("login:admin", limit=5, window_seconds=300)
    # no exception raised


def test_exceeding_the_limit_raises_rate_limit_error() -> None:
    for _ in range(5):
        redis_cache.check_and_increment("login:admin", limit=5, window_seconds=300)

    with pytest.raises(RateLimitError):
        redis_cache.check_and_increment("login:admin", limit=5, window_seconds=300)


def test_different_keys_have_independent_counters() -> None:
    for _ in range(5):
        redis_cache.check_and_increment("login:admin", limit=5, window_seconds=300)

    # a different username's attempts aren't affected by "admin"'s exhausted limit
    redis_cache.check_and_increment("login:someone-else", limit=5, window_seconds=300)
