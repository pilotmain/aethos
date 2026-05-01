"""Phase 43 — canonical event shape with optional ``task_id`` for Mission Control / SSE."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.events.bus import publish


def emit_unified_event(
    event_type: str,
    *,
    task_id: str | None = None,
    user_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Publish a bus event using the Phase 43 envelope::

        type, task_id, timestamp, payload[, user_id]

    ``publish`` also normalizes ``mission_id`` / ``agent`` for backward compatibility.
    """
    ev: dict[str, Any] = {
        "type": event_type,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload or {}),
    }
    if user_id is not None:
        ev["user_id"] = user_id
    publish(ev)


__all__ = ["emit_unified_event"]
