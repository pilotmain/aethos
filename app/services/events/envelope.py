"""Standard runtime event envelope for Mission Control (Phase 14–15)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.events.bus import publish


def emit_runtime_event(
    event_type: str,
    *,
    mission_id: str | None = None,
    agent: str | None = None,
    user_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Publish a bus event with the locked shape::

        type, timestamp, mission_id, agent, payload[, user_id]

    ``mission_id`` and ``agent`` are always present (``null`` when not applicable).
    """
    ev: dict[str, Any] = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mission_id": mission_id,
        "agent": agent,
        "payload": dict(payload or {}),
    }
    if user_id is not None:
        ev["user_id"] = user_id
    publish(ev)


__all__ = ["emit_runtime_event"]
