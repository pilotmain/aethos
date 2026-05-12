"""Gateway NL: show Anthropic intelligence preset / effective model."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import parse_intelligence_query_intent
from app.services.llm_intelligence import build_intelligence_public_dict, format_intelligence_gateway_markdown


def try_gateway_llm_intelligence_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """Read-only model tier info (no secrets)."""
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None
    if parse_intelligence_query_intent(raw) is None:
        return None
    _ = db

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    info = build_intelligence_public_dict()
    body = format_intelligence_gateway_markdown(info)
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(body.strip(), source="llm_intelligence", user_text=raw),
        "intent": "intelligence_info",
    }


__all__ = ["try_gateway_llm_intelligence_turn"]
