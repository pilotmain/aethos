"""Execution context passed through gateway → workers → tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GatewayContext:
    """Mutable context for one gateway invocation."""

    user_id: str
    channel: str = "web"
    locale: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
