# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Redis-backed distributed locks for gateway lane serialization (multi-worker)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_redis_clients: dict[str, Any] = {}


def _import_redis() -> Any:
    try:
        import redis  # noqa: PLC0415
    except ImportError:
        return None
    return redis


def reset_distributed_lane_redis_clients() -> None:
    """Close cached Redis clients (tests / reload)."""
    for _url, c in list(_redis_clients.items()):
        try:
            c.close()
        except Exception:  # noqa: BLE001
            pass
    _redis_clients.clear()


def _get_client(redis_url: str) -> Any | None:
    """Return a shared :class:`redis.Redis` client or None if redis is missing or unreachable."""
    url = (redis_url or "").strip()
    if not url:
        return None
    if url in _redis_clients:
        c = _redis_clients[url]
        try:
            c.ping()
            return c
        except Exception:  # noqa: BLE001
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
            del _redis_clients[url]

    redis_mod = _import_redis()
    if redis_mod is None:
        logger.warning("redis package not installed; install redis>=5 for distributed lane locks")
        return None
    try:
        c = redis_mod.Redis.from_url(
            url,
            socket_connect_timeout=2.0,
            socket_timeout=30.0,
        )
        c.ping()
        _redis_clients[url] = c
        return c
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis connection failed for lane locks (%s): %s", url.split("@")[-1], exc)
        return None


@contextmanager
def lane_lock_acquire(
    session_id: str,
    *,
    redis_url: str,
    lock_ttl_s: int = 300,
    blocking_timeout_s: float = 120.0,
) -> Iterator[None]:
    """
    Serialize work for one lane key across processes (``nexa:lane:{session_id}``).

    ``lock_ttl_s`` is the Redis key TTL (auto-release if a worker dies mid-turn).
    ``blocking_timeout_s`` caps wait time when another worker holds the lock.
    """
    c = _get_client(redis_url)
    if c is None:
        raise RuntimeError("Redis client unavailable for distributed lane lock")

    lane = (session_id or "").strip() or "default"
    key = f"nexa:lane:{lane}"
    lock = c.lock(
        key,
        timeout=lock_ttl_s,
        blocking_timeout=blocking_timeout_s,
        thread_local=True,
    )
    acquired = False
    try:
        acquired = lock.acquire(blocking=True, blocking_timeout=blocking_timeout_s)
        if not acquired:
            raise TimeoutError(f"could not acquire lane lock within {blocking_timeout_s}s: {key}")
        yield
    finally:
        if acquired:
            try:
                lock.release()
            except Exception as exc:  # noqa: BLE001
                logger.debug("lane lock release ignored: %s", exc)


__all__ = ["lane_lock_acquire", "reset_distributed_lane_redis_clients"]
