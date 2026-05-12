# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Single funnel so adapters cannot bypass privacy + mission routing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


def route_inbound(
    text: str,
    user_id: str,
    *,
    db: Session | None = None,
    channel: str = "web",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """All channels must call this (or :meth:`NexaGateway.handle_message` directly)."""
    ctx = GatewayContext.from_channel(user_id, channel, metadata)
    return NexaGateway().handle_message(ctx, text, db=db)


__all__ = ["route_inbound"]
