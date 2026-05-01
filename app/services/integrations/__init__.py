"""External connectors — Gmail, Calendar, GitHub, generic HTTP (Phase 22 stubs)."""

from __future__ import annotations

from typing import Any, Callable


class ConnectorRegistry:
    """Register connector factories; implementations stay behind privacy review."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, factory: Callable[..., Any]) -> None:
        self._factories[name] = factory

    def names(self) -> list[str]:
        return sorted(self._factories.keys())


default_registry = ConnectorRegistry()


__all__ = ["ConnectorRegistry", "default_registry"]
