# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin lifecycle events (Phase 2 Step 8)."""

from __future__ import annotations

from collections import deque
from typing import Any

from app.runtime.runtime_state import utc_now_iso

_EVENTS: deque[dict[str, Any]] = deque(maxlen=200)


def emit_plugin_event(event_type: str, **fields: Any) -> dict[str, Any]:
    row = {"type": event_type, "timestamp": utc_now_iso(), **fields}
    _EVENTS.appendleft(row)
    return row


def recent_plugin_events(*, limit: int = 40) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 200))
    return list(_EVENTS)[:lim]
