"""Execution context passed through gateway → workers → tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GatewayContext:
    """Mutable context for one gateway invocation (Phase 36 — approval + LLM metadata)."""

    user_id: str
    channel: str = "web"
    locale: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_metadata(cls, user_id: str, channel: str, metadata: dict[str, Any] | None) -> GatewayContext:
        return cls(user_id=user_id, channel=channel, metadata=dict(metadata or {}))
