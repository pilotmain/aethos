"""Normalize channel identifiers for session-scoped orchestration."""

from __future__ import annotations

KNOWN_CHANNELS = frozenset(
    {"web", "api", "telegram", "slack", "sms", "whatsapp", "email", "automation", "cli"}
)


def normalize_channel(raw: str | None) -> str:
    c = (raw or "web").strip().lower() or "web"
    return c if c in KNOWN_CHANNELS else "web"
