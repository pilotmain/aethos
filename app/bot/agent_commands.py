"""
Telegram commands for orchestration sub-agents (Phase 37).

Uses /subagent to avoid clashing with /agents (LLM catalog) and /agent (custom agents).
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.core.db import SessionLocal
from app.services.agent.activity_tracker import get_activity_tracker
from app.core.config import get_settings
from app.services.sub_agent_registry import AgentRegistry, AgentStatus
from app.services.sub_agent_router import telegram_agent_registry_chat_id
from app.services.telegram_service import TelegramService

telegram_service = TelegramService()


def _user_web_registry_scope(app_user_id: str) -> str:
    """Same ``parent_chat_id`` as :func:`~app.api.routes.agent_spawn._web_chat_scope` (API / Mission Control)."""
    uid = (app_user_id or "").strip()[:128]
    return f"web:{uid}:default"


def telegram_subagent_scopes(telegram_chat_id: int, app_user_id: str) -> list[str]:
    """In-chat registry scope plus the user's web scope so API-created agents are visible in Telegram."""
    scopes: list[str] = [telegram_agent_registry_chat_id(telegram_chat_id)]
    uid = (app_user_id or "").strip()
    if uid:
        web_scope = _user_web_registry_scope(uid)
        if web_scope not in scopes:
            scopes.append(web_scope)
        # Phase 61 — match API / Mission Control: registry rows may use bare tg_<digits>
        if uid.startswith("tg_") and uid not in scopes:
            scopes.append(uid)
    return scopes


async def subagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatch: list | delete | pause | resume | status <name> [confirm]."""
    if not update.effective_user or not update.message or not update.effective_chat:
        return

    args = list(context.args or [])
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return

        scopes = telegram_subagent_scopes(update.effective_chat.id, link.app_user_id)
        registry = AgentRegistry()
        tracker = get_activity_tracker()

        if not args or args[0].lower() in ("help", "-h", "--help"):
            await update.message.reply_text(
                "Orchestration agents (sub-agents)\n\n"
                "• /subagent list — roster + success rate\n"
                "• /subagent create <name> <domain> — spawn in this chat (Telegram scope)\n"
                "• /subagent status <name> — details\n"
                "• /subagent pause <name>\n"
                "• /subagent resume <name>\n"
                "• /subagent delete <name> confirm — remove permanently\n\n"
                "Domains include **qa**, **marketing**, **git**, **vercel**, **railway**, **ops**, **test**, **security**, **general**.\n\n"
                "Includes agents created via the API / Mission Control (same account).\n"
                "Also: /agent_status (quick list)."
            )
            return

        sub = args[0].lower()

        if sub == "create":
            if len(args) < 3:
                await update.message.reply_text("Usage: /subagent create <name> <domain>")
                return
            settings = get_settings()
            if not bool(getattr(settings, "nexa_agent_orchestration_enabled", False)):
                await update.message.reply_text(
                    "Sub-agent orchestration is off. Set NEXA_AGENT_ORCHESTRATION_ENABLED=true."
                )
                return
            name_new = args[1].strip().lstrip("@")
            domain_new = args[2].strip().lower()
            if not name_new or not domain_new:
                await update.message.reply_text("Name and domain are required.")
                return
            if registry.get_agent_by_name_in_scopes(name_new, scopes):
                await update.message.reply_text(
                    f"An orchestration agent named @{name_new} already exists in this chat or your workspace."
                )
                return
            tscope = telegram_agent_registry_chat_id(update.effective_chat.id)
            trusted = bool(getattr(settings, "nexa_agent_auto_approve", False))
            spawned = registry.spawn_agent(name_new, domain_new, tscope, trusted=trusted)
            if not spawned:
                await update.message.reply_text(
                    "Could not create agent (limit reached, duplicate, or orchestration blocked)."
                )
                return
            get_activity_tracker().log_action(
                agent_id=spawned.id,
                agent_name=spawned.name,
                action_type="created",
                metadata={"via": "telegram_subagent_create", "parent_chat_id": tscope},
            )
            await update.message.reply_text(
                f"✅ @{spawned.name} created ({spawned.domain}). Scope: this Telegram chat."
            )
            return

        if sub == "list":
            agents = registry.list_agents_merged(scopes)
            if not agents:
                await update.message.reply_text(
                    "No orchestration agents in this chat yet. "
                    "Enable NEXA_AGENT_ORCHESTRATION_ENABLED and spawn from Mission Control or the API."
                )
                return
            lines = ["Orchestration agents", ""]
            emoji = {
                "idle": "🟢",
                "busy": "🟡",
                "paused": "⏸️",
                "error": "🔴",
                "terminated": "⚫",
            }
            for agent in agents:
                stats = tracker.get_agent_statistics(agent.id)
                em = emoji.get(agent.status.value, "⚪")
                lines.append(f"{em} @{agent.name} ({agent.domain})")
                lines.append(f"   Success: {stats.get('success_rate', 100):.0f}%  ·  actions: {stats.get('total_actions', 0)}")
                lines.append("")
            lines.append("Delete: /subagent delete <name> confirm")
            await update.message.reply_text("\n".join(lines).strip()[:9000])
            return

        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /subagent <list|create|status|pause|resume|delete> … "
                "(create needs name + domain)"
            )
            return

        name = args[1].strip().lstrip("@")
        agent = registry.get_agent_by_name_in_scopes(name, scopes)
        if not agent:
            await update.message.reply_text(
                f"No orchestration agent named '{name}' for this chat/account "
                f"(checked Telegram scope and your API/Mission Control workspace)."
            )
            return

        if sub == "status":
            stats = tracker.get_agent_statistics(agent.id)
            md = dict(agent.metadata or {})
            task = md.get("current_task")
            caps = list(agent.capabilities or [])[:12]
            cap_s = ", ".join(caps) if caps else "—"
            lines = [
                f"@{agent.name} ({agent.domain})",
                f"Status: {agent.status.value}",
                f"Trusted (auto-approve path): {bool(agent.trusted)}",
                f"Success rate (30d): {stats.get('success_rate', 100):.1f}%",
                f"Actions (30d): {stats.get('total_actions', 0)}",
                f"Skills: {cap_s}",
            ]
            if task:
                lines.append(f"Current task: {task[:500]}")
            await update.message.reply_text("\n".join(lines)[:9000])
            return

        if sub == "pause":
            registry.patch_agent(agent.id, status=AgentStatus.PAUSED)
            tracker.log_action(agent_id=agent.id, agent_name=agent.name, action_type="paused")
            await update.message.reply_text(f"⏸️ @{agent.name} paused.")
            return

        if sub == "resume":
            if agent.status == AgentStatus.TERMINATED:
                await update.message.reply_text("Cannot resume a terminated agent.")
                return
            registry.patch_agent(agent.id, status=AgentStatus.IDLE)
            tracker.log_action(agent_id=agent.id, agent_name=agent.name, action_type="resumed")
            await update.message.reply_text(f"▶️ @{agent.name} resumed (idle).")
            return

        if sub == "delete":
            if len(args) < 3 or args[2].lower() != "confirm":
                await update.message.reply_text(
                    f"⚠️ To permanently delete @{name}, run:\n"
                    f"/subagent delete {name} confirm"
                )
                return
            tracker.log_action(
                agent_id=agent.id,
                agent_name=agent.name,
                action_type="deleted",
                metadata={"via": "telegram", "scopes": scopes, "parent_chat_id": agent.parent_chat_id},
            )
            if registry.remove_agent(agent.id):
                await update.message.reply_text(f"✅ Agent @{name} removed.")
            else:
                await update.message.reply_text("Could not remove agent (already gone).")
            return

        await update.message.reply_text("Unknown subcommand. Try /subagent help.")
    finally:
        db.close()


__all__ = ["subagent_command", "telegram_subagent_scopes"]
