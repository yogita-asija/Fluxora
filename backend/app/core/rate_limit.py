"""Brute-force protection for login: after N failed attempts an account is locked for a window.

Failures are counted per account (hashed email), not per IP, so an attacker can't dodge the
limit by rotating addresses. The trade-off is that someone can deliberately lock a known
email out for the window; Nginx also rate-limits /api/v1/auth/ per IP at the edge.
"""

import hashlib
import logging
import threading
import time
from functools import lru_cache
from typing import Protocol

import redis

from app.core.config import get_settings
from app.core.errors import TooManyRequestsError

logger = logging.getLogger(__name__)


class CounterStore(Protocol):
    def get(self, key: str) -> int: ...
    def incr(self, key: str, ttl_seconds: int) -> int: ...
    def ttl(self, key: str) -> int: ...
    def delete(self, key: str) -> None: ...


class MemoryStore:
    """Per-process store for tests and single-process development."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def _live(self, key: str) -> tuple[int, float] | None:
        entry = self._data.get(key)
        if entry and entry[1] <= time.monotonic():
            del self._data[key]
            return None
        return entry

    def get(self, key: str) -> int:
        with self._lock:
            entry = self._live(key)
            return entry[0] if entry else 0

    def incr(self, key: str, ttl_seconds: int) -> int:
        with self._lock:
            entry = self._live(key)
            if entry is None:
                self._data[key] = (1, time.monotonic() + ttl_seconds)
                return 1
            self._data[key] = (entry[0] + 1, entry[1])
            return entry[0] + 1

    def ttl(self, key: str) -> int:
        with self._lock:
            entry = self._live(key)
            return max(0, int(entry[1] - time.monotonic())) if entry else 0

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class RedisStore:
    """Shared across API replicas."""

    def __init__(self, client: "redis.Redis") -> None:
        self.client = client

    def get(self, key: str) -> int:
        return int(self.client.get(key) or 0)

    def incr(self, key: str, ttl_seconds: int) -> int:
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds, nx=True)  # start the window on the first failure only
        count, _ = pipe.execute()
        return int(count)

    def ttl(self, key: str) -> int:
        return max(0, int(self.client.ttl(key)))

    def delete(self, key: str) -> None:
        self.client.delete(key)


class LoginThrottle:
    def __init__(self, store: CounterStore, max_attempts: int, window_seconds: int) -> None:
        self.store = store
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    @staticmethod
    def _key(identifier: str) -> str:
        digest = hashlib.sha256(identifier.strip().lower().encode()).hexdigest()[:32]
        return f"login_fail:{digest}"

    def check(self, identifier: str) -> None:
        """Raises TooManyRequestsError if the account is locked."""
        key = self._key(identifier)
        try:
            if self.store.get(key) >= self.max_attempts:
                raise TooManyRequestsError(
                    "Too many failed login attempts. Try again later.",
                    retry_after=self.store.ttl(key),
                )
        except redis.RedisError:
            # Fail open: a Redis outage must not lock everyone out of the app.
            logger.warning("Login throttle unavailable (Redis error); allowing attempt")

    def record_failure(self, identifier: str) -> None:
        try:
            self.store.incr(self._key(identifier), self.window_seconds)
        except redis.RedisError:
            logger.warning("Login throttle unavailable (Redis error); failure not recorded")

    def reset(self, identifier: str) -> None:
        try:
            self.store.delete(self._key(identifier))
        except redis.RedisError:
            logger.warning("Login throttle unavailable (Redis error); counter not reset")


@lru_cache
def get_login_throttle() -> LoginThrottle:
    settings = get_settings()
    if settings.redis_url:
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        store: CounterStore = RedisStore(client)
    else:
        store = MemoryStore()
    return LoginThrottle(store, settings.login_max_attempts, settings.login_window_seconds)
