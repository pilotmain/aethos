"""Gateway NL: explicit ``Development …`` / ``Dev …`` coding asks (before deploy routing)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import parse_development_task_intent
from app.services.sub_agent_registry import AgentRegistry, SubAgent
from app.services.sub_agent_router import orchestration_chat_key


def _pick_dev_agent(chat_key: str, app_user_id: str) -> SubAgent | None:
    """Prefer a backend/frontend/qa-ish agent in this chat, else any name containing ``dev``."""
    reg = AgentRegistry()
    in_chat = reg.list_agents(chat_key)
    scored: list[tuple[int, SubAgent]] = []
    for ag in in_chat:
        nm = (ag.name or "").lower()
        dom = (ag.domain or "").lower()
        score = 99
        if "dev" in nm or nm.endswith("developer_agent"):
            score = 0
        elif dom in ("backend", "frontend", "qa", "test"):
            score = 1
        scored.append((score, ag))
    scored.sort(key=lambda t: (t[0], len(t[1].name or "")))
    for sc, ag in scored:
        if sc <= 1:
            return ag
    for ag in reg.list_agents_for_app_user(app_user_id):
        nm = (ag.name or "").lower()
        if "dev" in nm:
            return ag
    return None


def try_development_nl_gateway_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    _ = db
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None
    parsed = parse_development_task_intent(raw)
    if not parsed:
        return None
    task = str(parsed.get("task") or "").strip()[:4_000]
    if not task:
        return None

    ck = orchestration_chat_key(gctx)
    ag = _pick_dev_agent(ck, uid)
    if ag is not None:
        an = (ag.name or "").strip() or "agent"
        return {
            "mode": "chat",
            "text": (
                "**Development task**\n\n"
                f"_{task}_\n\n"
                f"To have a coding agent execute this in your workspace, message it directly, for example:\n\n"
                f"`@{an} {task}`\n\n"
                f"_If **@{an}** was created in another chat, open Mission Control there or say **create a developer agent** in this chat._"
            ),
            "intent": "development_nl_routed",
        }

    return {
        "mode": "chat",
        "text": (
            "**Development task**\n\n"
            f"_{task}_\n\n"
            "I don’t auto-edit files from this phrase alone. **Create a developer sub-agent** in this chat "
            "(Mission Control or say **create a developer agent**), then assign work with:\n\n"
            "`@your_agent_name …`"
        ),
        "intent": "development_nl_hint",
    }


__all__ = ["try_development_nl_gateway_turn"]
