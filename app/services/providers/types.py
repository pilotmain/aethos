"""Provider request/response shapes for the outbound gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderRequest:
    user_id: str
    mission_id: str | None
    agent_handle: str | None
    provider: str
    model: str | None
    purpose: str
    payload: dict[str, Any]
    allow_external: bool = True


@dataclass
class ProviderResponse:
    ok: bool
    provider: str
    model: str | None
    output: dict[str, Any] | str | None
    redactions: list[dict[str, Any]] = field(default_factory=list)
    blocked: bool = False
    error: str | None = None
