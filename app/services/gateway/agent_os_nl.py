"""Gateway NL hooks for Agentic OS status dashboard."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import parse_status_intent
from app.services.observability import get_observability, parse_observability_intent
from app.services.status_monitor import get_status_monitor


def try_agent_os_status_turn(
    gctx: GatewayContext,
    text: str,
    db: Session | None,
) -> dict[str, Any] | None:
    """Return status dashboard markdown when the user asks for progress/heartbeat."""
    _ = db
    kind = parse_observability_intent(text)
    if kind:
        if bool(getattr(get_settings(), "nexa_observability_enabled", False)):
            obs = get_observability()
            if kind == "alerts":
                rows = obs.list_active_alerts(40)
                body = "## Alerts\n\n"
                body += "\n".join(
                    f"- **{a.get('severity')}** {a.get('title')}: {a.get('message')}" for a in rows
                ) or "_No active alerts._"
            elif kind == "metrics":
                recent = obs.list_recent_metrics(20)
                body = "## Metrics\n\n"
                body += "\n".join(f"- **{m.name}**: {m.value} {m.unit}" for m in recent) or "_No metrics recorded._"
            else:
                body = obs.get_dashboard_markdown()
            return {
                "mode": "chat",
                "text": body,
                "intent": "observability_dashboard",
                "observability": True,
            }
        obs = get_observability()
        note = (
            "_Optional: **NEXA_OBSERVABILITY_ENABLED=true** for full traces + alert fan-out._\n\n"
        )
        uid = (gctx.user_id or "").strip()
        if kind == "metrics":
            recent = obs.list_recent_metrics(40)
            lines = "\n".join(f"- **{m.name}**: {m.value} {m.unit}" for m in recent)
            body = note + "## Metrics\n\n" + (lines or "_No metrics recorded yet._")
        elif kind == "alerts":
            rows = obs.list_active_alerts(40)
            lines = "\n".join(
                f"- **{a.get('severity')}** {a.get('title')}: {a.get('message')}" for a in rows
            )
            body = note + "## Alerts\n\n" + (lines or "_No alerts recorded._")
        elif uid:
            mon = get_status_monitor()
            mon.tick()
            body = note + mon.get_dashboard_markdown(uid)
        else:
            body = note + obs.get_dashboard_markdown()
        return {
            "mode": "chat",
            "text": body,
            "intent": "observability_dashboard",
            "observability": True,
        }
    parsed = parse_status_intent(text)
    if not parsed:
        return None
    uid = (gctx.user_id or "").strip()
    if not uid:
        return None
    mon = get_status_monitor()
    mon.tick()
    intent = str(parsed.get("intent") or "")
    if intent == "active_work":
        body = mon.format_who_is_working(uid) + "\n\n---\n\n" + mon.get_dashboard_markdown(uid)
    else:
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
