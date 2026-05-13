# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Per-lane serialization for gateway turns (OpenClaw-style lane queue, in-process).

Each ``gateway_lane_id`` maps to one :class:`threading.Lock`. Only one thread may
execute a full gateway turn for that lane at a time. Different lanes run concurrently.

For multi-instance deployments, replace with a distributed lock / queue (e.g. Redis).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Dict, Iterator

from app.services.gateway.context import GatewayContext


class SessionQueueManager:
    """Serialize gateway work per logical chat/session (thread-safe, in-memory)."""

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
    ws = str(ex.get("web_session_id") or "default").strip()[:200] or "default"
    return f"{channel}:{uid}:ws{ws}"


__all__ = ["SessionQueueManager", "gateway_lane_id", "session_queue"]
