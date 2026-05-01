"""Single funnel so adapters cannot bypass privacy + mission routing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

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
    return NexaGateway().handle_message(text, user_id, db=db, channel=channel, metadata=metadata)


__all__ = ["route_inbound"]
