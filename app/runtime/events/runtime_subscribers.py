"""Runtime event subscriber hooks (reserved for Phase 2 fan-out)."""

from __future__ import annotations

from typing import Any, Callable

from app.services.events.bus import subscribe, unsubscribe


def subscribe_runtime(callback: Callable[[dict[str, Any]], None]) -> Callable[[dict[str, Any]], None]:
    return subscribe(callback)


def unsubscribe_runtime(callback: Callable[[dict[str, Any]], None]) -> None:
    unsubscribe(callback)
