from __future__ import annotations

from typing import Any


def channel_audit_metadata(normalized_message: dict[str, Any]) -> dict[str, Any]:
    """Subset of normalized payload for audit/trust events (Phase 3 wiring)."""
    meta = normalized_message.get("metadata") or {}
    return {
        "channel": normalized_message.get("channel"),
        "channel_user_id": normalized_message.get("channel_user_id"),
        "channel_message_id": meta.get("channel_message_id"),
        "channel_thread_id": meta.get("channel_thread_id"),
    }


def build_channel_origin(normalized_message: dict[str, Any]) -> dict[str, Any]:
    """Full origin dict for core path / ContextVar (audit helper + chat/session ids)."""
    meta = normalized_message.get("metadata") or {}
    out: dict[str, Any] = {
        **channel_audit_metadata(normalized_message),
        "channel_chat_id": meta.get("channel_chat_id"),
    }
    if meta.get("web_session_id") is not None:
        out["web_session_id"] = meta.get("web_session_id")
    if meta.get("slack_team_id") is not None:
        out["slack_team_id"] = meta.get("slack_team_id")
    return out
