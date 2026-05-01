"""Slack → Nexa gateway funnel via :func:`~app.services.channels.router.route_inbound` (Phase 42)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.channels.router import route_inbound


def slack_inbound_via_gateway(db: Session, normalized_message: dict[str, Any]) -> dict[str, Any]:
    """
    Same outbound shape as :func:`~app.services.channel_gateway.router.handle_incoming_channel_message`
    so Slack outbound posting stays unchanged.
    """
    text = str(normalized_message.get("message") or normalized_message.get("text") or "").strip()
    uid = str(
        normalized_message.get("user_id") or normalized_message.get("app_user_id") or ""
    ).strip()
    meta = dict(normalized_message.get("metadata") or {})
    meta.setdefault("via_slack_route_inbound", True)
    raw = route_inbound(text, uid, db=db, channel="slack", metadata=meta)
    reply = str(raw.get("text") or "").strip()
    return {
        "message": reply,
        "permission_required": None,
        "response_kind": "chat",
        "metadata": {"channel": "slack", "channel_user_id": normalized_message.get("channel_user_id")},
        "intent": raw.get("intent"),
        "agent_key": None,
        "related_job_ids": [],
        "sources": [],
        "web_tool_line": None,
        "usage_summary": None,
        "request_id": None,
        "decision_summary": None,
        "system_events": [],
    }


__all__ = ["slack_inbound_via_gateway"]
