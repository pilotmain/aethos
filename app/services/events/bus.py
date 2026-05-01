"""Streamable in-process event bus — deque history + optional subscriber push (WebSocket/SSE)."""

from __future__ import annotations

from collections import deque
from typing import Any, Callable

EVENTS: deque[dict[str, Any]] = deque(maxlen=10000)

SUBSCRIBERS: list[Callable[[dict[str, Any]], None]] = []


def publish(event: dict[str, Any]) -> None:
    ev = dict(event)
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
