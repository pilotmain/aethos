"""Gateway NL hooks for Agentic OS status dashboard."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import parse_status_intent
from app.services.status_monitor import get_status_monitor


def try_agent_os_status_turn(
    gctx: GatewayContext,
    text: str,
    db: Session | None,
) -> dict[str, Any] | None:
    """Return status dashboard markdown when the user asks for progress/heartbeat."""
    _ = db
    parsed = parse_status_intent(text)
    if not parsed:
        return None
    uid = (gctx.user_id or "").strip()
    if not uid:
        return None
    mon = get_status_monitor()
    mon.tick()
    body = mon.get_dashboard_markdown(uid)
    interval = int(getattr(get_settings(), "nexa_agent_heartbeat_interval", 30))
    if parsed.get("intent") == "heartbeat":
        body += f"\n\n_Configured agent heartbeat interval: **{interval}s**._"
    return {
        "mode": "chat",
        "text": body,
        "intent": str(parsed.get("intent") or "status_dashboard"),
        "agent_os_status": True,
    }


__all__ = ["try_agent_os_status_turn"]
