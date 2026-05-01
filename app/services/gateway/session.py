"""User session handles for gateway — durable session ids keyed by channel + user."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GatewaySessionRef:
    """Minimal session reference until full session store lands."""

    user_id: str
    channel: str
    session_key: str
