"""Streamable in-process event bus — deque history + optional subscriber push (WebSocket/SSE)."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

EVENTS: deque[dict[str, Any]] = deque(maxlen=10000)

SUBSCRIBERS: list[Callable[[dict[str, Any]], None]] = []


def _normalize_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    return {"value": raw}


def publish(event: dict[str, Any]) -> None:
    """Append an event; coerce to the Phase 15 runtime schema (type, timestamp, mission_id, agent, payload)."""
    ev = dict(event)
    if "type" not in ev or not isinstance(ev["type"], str) or not ev["type"].strip():
        raise ValueError("bus event requires non-empty string 'type'")
    ev.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    ev["payload"] = _normalize_payload(ev.get("payload"))
    ev.setdefault("mission_id", None)
    ev.setdefault("agent", None)
    EVENTS.append(ev)
    for cb in list(SUBSCRIBERS):
        try:
            cb(ev)
        except Exception:
            pass


def list_events() -> list[dict[str, Any]]:
    return list(EVENTS)


def subscribe(callback: Callable[[dict[str, Any]], None]) -> Callable[[dict[str, Any]], None]:
    SUBSCRIBERS.append(callback)
    return callback


def unsubscribe(callback: Callable[[dict[str, Any]], None]) -> None:
    try:
        SUBSCRIBERS.remove(callback)
    except ValueError:
        pass


def clear_events() -> None:
    EVENTS.clear()
