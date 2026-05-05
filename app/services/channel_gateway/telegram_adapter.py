from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.services.channel_gateway.base import ChannelAdapter
from app.services.channel_gateway.identity import resolve_channel_user
from app.services.telegram_service import TelegramService

_telegram_adapter: TelegramAdapter | None = None


def _telegram_display_name(user: Any) -> str | None:
    if user is None:
        return None
    fn = getattr(user, "full_name", None)
    if fn:
        return str(fn)
    first = getattr(user, "first_name", None)
    last = getattr(user, "last_name", None)
    parts = [p for p in (first, last) if p]
    return " ".join(parts) if parts else None


class TelegramAdapter(ChannelAdapter):
    channel = "telegram"

    def __init__(self, telegram_service: TelegramService | None = None) -> None:
        self._telegram = telegram_service or TelegramService()

    def resolve_app_user_id(self, db: Session, raw_event: Any) -> str:
        u: Update = raw_event
        if not u.effective_user or not u.effective_chat:
            raise ValueError("Telegram update missing user or chat")
        eu = u.effective_user
        default_uid = self._telegram.link_user(
            db,
            telegram_user_id=eu.id,
            chat_id=u.effective_chat.id,
            username=eu.username,
        )
        return resolve_channel_user(
            db,
            channel=self.channel,
            channel_user_id=str(eu.id),
            default_user_id=default_uid,
            display_name=_telegram_display_name(eu),
            username=eu.username,
        )

    def normalize_message(self, raw_event: Any, *, app_user_id: str) -> dict[str, Any]:
        u: Update = raw_event
        eu = u.effective_user
        text = ""
        if u.message and u.message.text:
            text = u.message.text
        ch_uid = str(eu.id) if eu else None
        msg = u.message
        thread_id = None
        if msg is not None:
            tid = getattr(msg, "message_thread_id", None)
            if tid is not None:
                thread_id = str(tid)
        meta = {
            "channel_message_id": str(msg.message_id) if msg else None,
            "channel_chat_id": str(u.effective_chat.id) if u.effective_chat else None,
            "channel_thread_id": thread_id,
            "username": eu.username if eu else None,
            "display_name": _telegram_display_name(eu),
            "update_id": u.update_id,
        }
        return {
            "channel": self.channel,
            "channel_user_id": ch_uid,
            "user_id": app_user_id,
            "app_user_id": app_user_id,
            "message": text,
            "text": text,
            "attachments": [],
            "metadata": meta,
        }


def get_telegram_adapter() -> TelegramAdapter:
    global _telegram_adapter
    if _telegram_adapter is None:
        _telegram_adapter = TelegramAdapter()
    return _telegram_adapter


def route_telegram_text_through_gateway(
    text: str,
    app_user_id: str,
    *,
    db: Session,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phase 34 — same admission as web: :func:`~app.services.channels.router.route_inbound`."""
    from app.services.channels.router import route_inbound

    return route_inbound(text, app_user_id, db=db, channel="telegram", metadata=metadata or {})


def register_telegram_handlers(application: Application) -> None:
    """Wire all Telegram handlers. Lazy-imports `telegram_bot` to avoid import cycles.

    Plain text messages hit ``telegram_bot.handle_incoming_text``, which routes non-slash
    lines through :func:`route_telegram_text_through_gateway` / :func:`~app.services.channels.router.route_inbound`.
    """
    from app.bot import budget_commands as budget_cmds
    from app.bot import org_commands as org_cmds
    from app.bot import project_commands as mission_ctrl
    from app.bot import social_commands as social_cmds
    from app.bot import telegram_bot as tb

    application.add_handler(CommandHandler("start", tb.start))
    application.add_handler(CommandHandler("help", tb.help_cmd))
    application.add_handler(CommandHandler("updates", tb.updates_cmd))
    application.add_handler(CommandHandler("usage", tb.usage_cmd))
    application.add_handler(CommandHandler("today", tb.today))
    application.add_handler(CommandHandler("overwhelmed", tb.overwhelmed))
    application.add_handler(CommandHandler("prefs", tb.prefs))
    application.add_handler(CommandHandler("memory", tb.memory_cmd))
    application.add_handler(CommandHandler("doc", tb.doc_cmd))
    application.add_handler(CommandHandler("command", tb.command_cmd))
    application.add_handler(CommandHandler("forget", tb.forget_cmd))
    application.add_handler(CommandHandler("soul", tb.soul_cmd))
    application.add_handler(CommandHandler("agents", tb.agents_cmd))
    application.add_handler(CommandHandler("agent", tb.user_agent_cmd))
    application.add_handler(CommandHandler("learning", tb.learning_cmd))
    application.add_handler(CommandHandler("access", tb.access_cmd))
    application.add_handler(CommandHandler("users", tb.users_cmd))
    application.add_handler(CommandHandler("keys", tb.keys_cmd))
    application.add_handler(CommandHandler("key", tb.key_cmd))
    application.add_handler(CommandHandler("host", tb.host_cmd))
    application.add_handler(CommandHandler("permissions", tb.permissions_cmd))
    application.add_handler(CommandHandler("workspace", tb.workspace_cmd))
    # Phase 27 — Mission Control (projects/tasks; /goal — /project is workspace + dev keys)
    application.add_handler(CommandHandler("goal", mission_ctrl.goal_cmd))
    application.add_handler(CommandHandler("task", mission_ctrl.task_cmd))
    application.add_handler(CommandHandler("tasks", mission_ctrl.tasks_cmd))
    application.add_handler(CommandHandler("assign", mission_ctrl.assign_cmd))
    application.add_handler(CommandHandler("claim", mission_ctrl.claim_cmd))
    application.add_handler(CommandHandler("unclaim", mission_ctrl.unclaim_cmd))
    application.add_handler(CommandHandler("done", mission_ctrl.done_cmd))
    application.add_handler(CommandHandler("mission", mission_ctrl.mission_cmd))
    application.add_handler(CommandHandler("mcstatus", mission_ctrl.mcstatus_cmd))
    # Phase 28 — work-hour (token) budgets per team member (/timesheet = usage history; /usage is LLM stats)
    application.add_handler(CommandHandler("budget", budget_cmds.budget_cmd))
    application.add_handler(CommandHandler("timesheet", budget_cmds.timesheet_cmd))
    application.add_handler(CommandHandler("workhours", budget_cmds.timesheet_cmd))
    # Phase 29 — multi-tenant workspaces (organizations / RBAC)
    application.add_handler(CommandHandler("org", org_cmds.org_cmd))
    application.add_handler(CommandHandler("projects", tb.nexa_projects_list_cmd))
    application.add_handler(CommandHandler("project", tb.nexa_project_cmd))
    application.add_handler(CommandHandler("projects", tb.projects_cmd))
    application.add_handler(CommandHandler("project", tb.project_cmd))
    application.add_handler(
        CallbackQueryHandler(tb.permission_inline_callback, pattern=r"^perm:(grant|deny):\d+$")
    )
    application.add_handler(CallbackQueryHandler(tb.job_inline_callback, pattern=r"^job:\d+:"))
    application.add_handler(CommandHandler("approve", tb.approve_cmd))
    application.add_handler(CommandHandler("deny", tb.deny_cmd))
    application.add_handler(CommandHandler("cancel", tb.cancel_cmd))
    application.add_handler(CommandHandler("why", tb.why_cmd))
    application.add_handler(CommandHandler("imagine", tb.imagine_cmd))
    application.add_handler(CommandHandler("tweet", social_cmds.tweet_cmd))
    application.add_handler(CommandHandler("search_tweets", social_cmds.search_tweets_cmd))
    application.add_handler(MessageHandler(filters.PHOTO, tb.handle_incoming_photo))
    application.add_handler(MessageHandler(filters.VOICE, tb.handle_incoming_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tb.handle_incoming_text))
