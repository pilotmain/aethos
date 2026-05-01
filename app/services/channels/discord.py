"""Discord inbound adapter — text fans into :func:`~app.services.channels.router.route_inbound`."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.channels.base import Channel
from app.services.channels.router import route_inbound


class DiscordChannel(Channel):
    name = "discord"

    def send(self, message: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"channel": self.name, "delivered": True, "message": message, "meta": metadata or {}}

    def receive(self, payload: dict[str, Any], *, db: Session | None = None) -> dict[str, Any]:
        text = str(payload.get("text") or payload.get("content") or "")
        uid = str(payload.get("user_id") or payload.get("discord_user_id") or "discord_user")
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None
        return route_inbound(text, uid, db=db, channel=self.name, metadata=meta)


__all__ = ["DiscordChannel"]
