"""Simple in-memory sliding-window rate limiter for public endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class SlidingWindowRateLimiter:
    """Thread-safe per-key sliding window rate limiter."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait a minute and try again.",
                )
            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = SlidingWindowRateLimiter()


def enforce_public_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing rate limits on public verification/reporting."""
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    key = f"{client_host}:{request.url.path}"
    rate_limiter.check(key=key, limit=settings.PUBLIC_RATE_LIMIT_PER_MINUTE, window_seconds=60)
