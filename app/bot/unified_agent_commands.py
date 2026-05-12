# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 48 — unified orchestration roster listing (Telegram + web chat)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.custom_agents import display_agent_handle, list_active_custom_agents


def format_unified_agents_list_reply(
    db: Session,
    app_user_id: str,
    *,
    telegram_chat_id: int | None = None,
) -> str:
    """Mission Control / Telegram — merged orchestration scopes + optional legacy LLM profiles."""
    from app.bot.agent_commands import telegram_subagent_scopes
    from app.services.agent.activity_tracker import get_activity_tracker
    from app.services.sub_agent_registry import AgentRegistry

    uid = (app_user_id or "").strip()
    reg = AgentRegistry()
    tracker = get_activity_tracker()

    if telegram_chat_id is not None:
        scopes = telegram_subagent_scopes(int(telegram_chat_id), uid)
        agents = reg.list_agents_merged(scopes)
    else:
        agents = reg.list_agents_for_app_user(uid)
    emoji = {
        "idle": "🟢",
        "busy": "🟡",
        "paused": "⏸️",
        "error": "🔴",
        "terminated": "⚫",
    }
    lines: list[str] = [
        "**Orchestration agents** (registry)",
        "",
    ]
    if not agents:
        lines.append(
            "_No orchestration agents yet._ Enable **NEXA_AGENT_ORCHESTRATION_ENABLED**, then:\n"
            "• `create two agents qa_agent and marketing_agent`\n"
            "• `/subagent create <name> <domain>`"
        )
    else:
        for ag in agents[:40]:
            em = emoji.get(ag.status.value, "⚪")
            stats = tracker.get_agent_statistics(ag.id)
            sr = float(stats.get("success_rate", 100.0) or 100.0)
            ta = int(stats.get("total_actions", 0) or 0)
            lines.append(f"{em} @{ag.name} · **{ag.domain}** · {ag.status.value}")
            lines.append(f"   Success ~{sr:.0f}% · actions {ta}")
            lines.append("")

    legacy = list_active_custom_agents(db, uid)
    if legacy:
        lines.append("—")
        lines.append("_Legacy LLM profiles (still usable via @mention; not in orchestration roster):_")
        for a in legacy[:15]:
            dh = display_agent_handle(a.agent_key)
            lines.append(f"• `{dh}` — {(a.description or a.display_name or '')[:120]}")
        lines.append("")
        lines.append("_New work should use orchestration handles (`*_agent`) or `/subagent create`._")

    lines.append("")
    lines.append("Commands: `/subagent list` · `/subagent status <name>` · `/subagent delete <name> confirm`")
    return "\n".join(lines).strip()[:9000]
