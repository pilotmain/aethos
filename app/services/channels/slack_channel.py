"""Slack-shaped adapter — inbound text routes through the Nexa gateway."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.channels.base import Channel
from app.services.channels.router import route_inbound


class SlackChannel(Channel):
    name = "slack"

    def send(self, message: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"channel": self.name, "delivered": True, "message": message, "meta": metadata or {}}

    def receive(self, payload: dict[str, Any], *, db: Session | None = None) -> dict[str, Any]:
        text = str(payload.get("text") or payload.get("event", {}).get("text") or "")
        uid = str(payload.get("user_id") or payload.get("slack_user_id") or "slack_user")
        return route_inbound(text, uid, db=db, channel=self.name, metadata=payload.get("metadata"))


__all__ = ["SlackChannel"]
