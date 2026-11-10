"""The login throttle's two storage backends behave the same, and Redis outages fail open."""

import os

import pytest
import redis

from app.core.errors import TooManyRequestsError
from app.core.rate_limit import LoginThrottle, MemoryStore, RedisStore

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL")


def make_stores():
    stores = [pytest.param(MemoryStore(), id="memory")]
    if TEST_REDIS_URL:
        client = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
        client.flushdb()
        stores.append(pytest.param(RedisStore(client), id="redis"))
    return stores


@pytest.mark.parametrize("store", make_stores())
def test_throttle_locks_after_max_attempts_and_resets(store):
    throttle = LoginThrottle(store, max_attempts=3, window_seconds=60)

    for _ in range(3):
        throttle.check("a@example.com")
        throttle.record_failure("a@example.com")

    with pytest.raises(TooManyRequestsError) as locked:
        throttle.check("a@example.com")
    assert 0 < int(locked.value.headers["Retry-After"]) <= 60
    throttle.check("b@example.com")  # other accounts unaffected

    throttle.reset("a@example.com")
    throttle.check("a@example.com")


@pytest.mark.parametrize("store", make_stores())
def test_identifier_is_case_and_whitespace_insensitive(store):
    throttle = LoginThrottle(store, max_attempts=1, window_seconds=60)
    throttle.record_failure("A@Example.com ")
    with pytest.raises(TooManyRequestsError):
        throttle.check("a@example.com")


def test_memory_store_window_expires(monkeypatch):
    import app.core.rate_limit as module

    now = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    store = MemoryStore()
    throttle = LoginThrottle(store, max_attempts=1, window_seconds=60)

    throttle.record_failure("a@example.com")
    with pytest.raises(TooManyRequestsError):
        throttle.check("a@example.com")

    now[0] += 61
    throttle.check("a@example.com")


def test_redis_outage_fails_open():
    dead = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2, socket_timeout=0.2)
    throttle = LoginThrottle(RedisStore(dead), max_attempts=1, window_seconds=60)

    throttle.record_failure("a@example.com")  # must not raise
    throttle.check("a@example.com")  # must not raise or lock anyone out
    throttle.reset("a@example.com")
