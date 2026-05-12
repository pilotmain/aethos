# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Provider request/response shapes for the outbound gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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
    db: "Session | None" = None


@dataclass
class ProviderResponse:
    ok: bool
    provider: str
    model: str | None
    output: dict[str, Any] | str | None
    redactions: list[dict[str, Any]] = field(default_factory=list)
    blocked: bool = False
    error: str | None = None
    token_estimate: int | None = None
    cost_estimate_usd: float | None = None
    payload_summary: dict[str, Any] | None = None
