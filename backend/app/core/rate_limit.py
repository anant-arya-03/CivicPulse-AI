"""A small in-memory rate limiter used as a FastAPI dependency.

Usage:
    @router.post("/login", dependencies=[Depends(RateLimit("login", times=10, seconds=60))])

Limitation: counts live in this process's memory, so they reset on restart and are not
shared between multiple backend processes. That is fine for the MVP; a shared store
(e.g. Redis) would be the upgrade path.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import RateLimitedError

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


class RateLimit:
    def __init__(self, scope: str, *, times: int, seconds: int) -> None:
        self.scope = scope
        self.times = times
        self.seconds = seconds

    def __call__(self, request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return

        client_ip = request.client.host if request.client else "unknown"
        key = f"{self.scope}:{client_ip}"
        now = time.monotonic()

        with _lock:
            hits = _hits[key]
            while hits and now - hits[0] > self.seconds:
                hits.popleft()
            if len(hits) >= self.times:
                retry_after = int(self.seconds - (now - hits[0])) + 1
                raise RateLimitedError(
                    "Too many attempts. Please wait a moment and try again.",
                    {"retry_after_seconds": retry_after},
                )
            hits.append(now)


def reset_rate_limits() -> None:
    """Clear all counters (used by tests)."""
    with _lock:
        _hits.clear()
