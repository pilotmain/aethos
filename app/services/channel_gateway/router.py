# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.channel_gateway.governance import check_channel_governance
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.normalized_message import validate_normalized_message
from app.services.channel_gateway.origin_context import bind_channel_origin


def handle_incoming_channel_message(
    db: Session,
    *,
    normalized_message: dict[str, Any],
) -> dict[str, Any]:
    """
    Single entry for normalized channel payloads into Nexa core (delegates to web_chat_service).

    Does not interpret intent, run tools, or enforce permissions — process_web_message does.
    """
    validate_normalized_message(normalized_message)
    uid = (normalized_message.get("user_id") or normalized_message.get("app_user_id") or "").strip()
    if not uid:
        raise ValueError("normalized_message must include user_id or app_user_id")
    deny = check_channel_governance(db, user_id=uid, normalized_message=normalized_message)
    if deny is not None:
        return deny
    text = normalized_message.get("message")
    if text is None:
        text = normalized_message.get("text") or ""
    meta = normalized_message.get("metadata") or {}
    username = meta.get("username")
    w_sid = meta.get("web_session_id")
    w_sid = ((w_sid if w_sid is not None else "default") or "default").strip()[:64] or "default"
    origin = build_channel_origin(normalized_message)
    # Lazy import: router must not pull executor/tool modules at import time.
    from app.services.web_chat_service import process_web_message

    # Match Slack/WhatsApp: set ContextVar for audit; do not pass channel_origin= to
    # process_web_message (it has no such parameter — that caused HTTP 500 on /web/chat).
    with bind_channel_origin(origin):
        result = process_web_message(
            db,
            uid,
            text,
            username=username,
            web_session_id=w_sid,
        )
    ch = normalized_message.get("channel") or "unknown"
    ch_uid = normalized_message.get("channel_user_id")
    out_meta: dict[str, Any] = {"channel": ch, "channel_user_id": ch_uid}
    pr = result.permission_required
    rk = (result.response_kind or "chat") or "chat"
    if pr is not None:
        rk = "permission_required"
    return {
        "message": result.reply or "",
        "permission_required": pr,
        "response_kind": rk,
        "metadata": out_meta,
        "intent": result.intent,
        "agent_key": result.agent_key,
        "related_job_ids": list(result.related_job_ids),
        "sources": list(result.sources) if result.sources else [],
        "web_tool_line": result.web_tool_line,
        "usage_summary": result.usage_summary,
        "request_id": result.request_id,
        "decision_summary": result.decision_summary,
        "system_events": list(result.system_events) if result.system_events else [],
    }
