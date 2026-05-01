"""Simple sliding-window rate limit for provider calls (per user_id)."""

from __future__ import annotations

import time
from typing import Any

_REQUEST_BUCKETS: dict[str, list[float]] = {}


def allow_provider_request(user_id: str, *, limit_per_minute: int) -> bool:
    if limit_per_minute <= 0:
        return True
    uid = (user_id or "anonymous").strip() or "anonymous"
    now = time.monotonic()
    window = 60.0
    bucket = _REQUEST_BUCKETS.setdefault(uid, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit_per_minute:
        return False
    bucket.append(now)
    return True


def reset_rate_limits_for_tests() -> None:
    """Clear buckets (pytest isolation)."""
    _REQUEST_BUCKETS.clear()


__all__ = ["allow_provider_request", "reset_rate_limits_for_tests"]
