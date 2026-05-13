# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Per-lane serialization for gateway turns (OpenClaw-style lane queue).

Single-process: each ``gateway_lane_id`` maps to a :class:`threading.Lock`.

Multi-worker: set ``NEXA_USE_DISTRIBUTED_QUEUE=true`` and ``REDIS_URL`` to use Redis
locks (``nexa:lane:*``) so the same session serializes across Uvicorn workers / hosts.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Dict, Iterator

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext

logger = logging.getLogger(__name__)


class SessionQueueManager:
    """Serialize gateway work per logical chat/session."""

    def __init__(self) -> None:
        self._meta = threading.Lock()
        self._locks: Dict[str, threading.Lock] = {}

    def _lock_for(self, session_id: str) -> threading.Lock:
        with self._meta:
            lk = self._locks.get(session_id)
            if lk is None:
                lk = threading.Lock()
                self._locks[session_id] = lk
            return lk

    @contextmanager
    def acquire(self, session_id: str) -> Iterator[None]:
        s = get_settings()
        use_redis = bool(getattr(s, "nexa_use_distributed_queue", False))
        url = (getattr(s, "redis_url", None) or "").strip()
        if use_redis and url:
            try:
                from app.services.distributed_lock import lane_lock_acquire

                with lane_lock_acquire(session_id, redis_url=url):
                    yield
                return
            except ImportError:
                logger.warning("NEXA_USE_DISTRIBUTED_QUEUE is set but redis is not installed; using in-process locks")
            except TimeoutError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "distributed lane lock failed (%s); falling back to in-process lock — "
                    "cross-worker serialization is not guaranteed",
                    exc,
                )

        lk = self._lock_for(session_id)
        lk.acquire()
        try:
            yield
        finally:
            lk.release()


session_queue = SessionQueueManager()


def gateway_lane_id(gctx: GatewayContext) -> str:
    """Stable lane key: channel + user + session-scoped id (web tab / Telegram chat)."""
    uid = (gctx.user_id or "anon").strip() or "anon"
    channel = (gctx.channel or "unknown").strip() or "unknown"
    ex = gctx.extras or {}
    if channel == "telegram":
        chat = str(ex.get("telegram_chat_id") or ex.get("chat_id") or uid).strip() or uid
        return f"{channel}:{uid}:c{chat}"
    if channel == "discord":
        chat = str(
            ex.get("discord_channel_id") or ex.get("channel_id") or ex.get("web_session_id") or uid
        ).strip() or uid
        return f"{channel}:{uid}:c{chat}"
    ws = str(ex.get("web_session_id") or "default").strip()[:200] or "default"
    return f"{channel}:{uid}:ws{ws}"


__all__ = ["SessionQueueManager", "gateway_lane_id", "session_queue"]
