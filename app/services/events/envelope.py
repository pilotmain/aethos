"""Standard runtime event envelope for Mission Control (Phase 14)."""

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
    **extra: Any,
) -> None:
    """
    Publish a bus event with a stable shape::

        type, timestamp, mission_id?, agent?, user_id?, payload
    """
    ev: dict[str, Any] = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload or {}),
    }
    if mission_id is not None:
        ev["mission_id"] = mission_id
    if agent is not None:
        ev["agent"] = agent
    if user_id is not None:
        ev["user_id"] = user_id
    for k, v in extra.items():
        if k in ev or v is None:
            continue
        ev[k] = v
    publish(ev)


__all__ = ["emit_runtime_event"]
