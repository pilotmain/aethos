"""Execution context passed through gateway → workers → tools (Phase 37)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GatewayContext:
    """
    Single carrier for user id, channel, permissions, and channel-specific extras.

    Prefer ``permissions`` / ``extras`` over ad-hoc metadata dicts at gateway boundaries.
    """

    user_id: str
    channel: str = "web"
    locale: str | None = None
    permissions: dict[str, Any] = field(default_factory=dict)
    approval_state: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_channel(
        cls,
        user_id: str,
        channel: str,
        payload: dict[str, Any] | None = None,
    ) -> GatewayContext:
        """Split legacy flat metadata into permissions + extras."""
        p = dict(payload or {})
        perms: dict[str, Any] = {}
        if "telegram_owner" in p:
            perms["owner"] = bool(p.pop("telegram_owner"))
        if "owner" in p and "owner" not in perms:
            perms["owner"] = bool(p.pop("owner"))
        if "telegram_role" in p:
            perms["telegram_role"] = p.pop("telegram_role")
        p.setdefault("via_gateway", True)
        return cls(user_id=user_id, channel=channel, permissions=perms, extras=p)

    @classmethod
    def from_metadata(cls, user_id: str, channel: str, metadata: dict[str, Any] | None) -> GatewayContext:
        """Alias for :meth:`from_channel` (transitional)."""
        return cls.from_channel(user_id, channel, metadata)
