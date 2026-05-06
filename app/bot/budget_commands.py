"""
Telegram — team work-hour / token budgets (Phase 28).

Commands: /budget, /timesheet (and /workhours)

Note: /usage is already reserved for AethOS LLM call stats; use /timesheet for member usage history.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.budget.tracker import BudgetTracker
from app.services.team import TeamRoster
from app.services.user_capabilities import BLOCKED_MSG, get_telegram_role

_roster = TeamRoster()
_tracker = BudgetTracker()


def _orch_scope(update: Update) -> str:
    """Orchestration roster scope (must match gateway ``telegram:<chat_id>``)."""
    from app.services.sub_agent_router import telegram_agent_registry_chat_id

    return telegram_agent_registry_chat_id(update.effective_chat.id if update.effective_chat else None)


def _strip_at(token: str) -> str:
    t = (token or "").strip()
    return t[1:].strip() if t.startswith("@") else t


async def _gate(update: Update) -> bool:
    if not update.effective_user or not update.message:
        return False
    s = get_settings()
    if not getattr(s, "nexa_budget_enabled", True):
        await update.message.reply_text("Work-hour budgets are disabled (NEXA_BUDGET_ENABLED).")
        return False
    db = SessionLocal()
    try:
        if get_telegram_role(update.effective_user.id, db) == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return False
    finally:
        db.close()
    return True


async def budget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update) or not update.message:
        return
    chat_id = _orch_scope(update)
    raw = (update.message.text or "").strip()
    parts = raw.split()
    if len(parts) == 1:
        members = _roster.list_members(chat_id)
        if not members:
            await update.message.reply_text("No team members in this chat. Add some with /team add …")
            return
        member_ids = [m.member_id for m in members]
        summary = _tracker.get_team_summary(member_ids)
        lines = [
            "💰 Team work-hour budget (tokens this period)",
            "",
            f"Team total: {summary['team_total_used']:,} / {summary['team_total_limit']:,} "
            f"({summary['team_percentage']:.0f}%)",
            f"Remaining (sum of limits): {summary['team_remaining']:,} tokens",
            "",
            "Members:",
        ]
        for m in members:
            ms = summary["members"].get(m.member_id, {})
            em = "🟢" if ms.get("can_execute") else "🔴"
            u = int(ms.get("used", 0) or 0)
            lim = int(ms.get("limit", 0) or 0)
            lines.append(f"{em} {m.display_name}: {u:,} / {lim:,} tokens")
        lines.append("")
        lines.append("Details: /budget @Name  ·  /timesheet @Name  ·  /budget set Name 2000000")
        await update.message.reply_text("\n".join(lines))
        return

    if len(parts) >= 2 and parts[1] == "set":
        if len(parts) < 4:
            await update.message.reply_text("Usage: /budget set <name> <monthly_limit>")
            return
        sub = _strip_at(parts[2])
        try:
            new_limit = int(parts[3].replace(",", ""))
        except ValueError:
            await update.message.reply_text("Monthly limit must be a number.")
            return
        member = _roster.get_member_by_name(sub, chat_id)
        if not member:
            await update.message.reply_text(f"No member named “{sub}” in this chat.")
            return
        _tracker.set_budget_limit(member.member_id, new_limit)
        await update.message.reply_text(
            f"✅ Monthly limit for {member.display_name} set to {new_limit:,} tokens."
        )
        return

    if len(parts) >= 2 and parts[1] == "adjust":
        if len(parts) < 4:
            await update.message.reply_text(
                "Usage: /budget adjust <name> +50000  (positive grants headroom; negative adds usage)"
            )
            return
        sub = _strip_at(parts[2])
        try:
            adj = int(parts[3].replace(",", ""))
        except ValueError:
            await update.message.reply_text("Adjustment must be an integer, e.g. +50000 or -1000.")
            return
        member = _roster.get_member_by_name(sub, chat_id)
        if not member:
            await update.message.reply_text(f"No member named “{sub}” in this chat.")
            return
        reason = " ".join(parts[4:]) if len(parts) > 4 else "Manual adjustment"
        _tracker.adjust_budget(member.member_id, adj, reason)
        sign = "+" if adj > 0 else ""
        await update.message.reply_text(
            f"✅ Budget adjusted for {member.display_name}: {sign}{adj:,} tokens\nReason: {reason}"
        )
        return

    # /budget Name or @Name — member detail
    name_tok = _strip_at(parts[1])
    member = _roster.get_member_by_name(name_tok, chat_id)
    if not member:
        await update.message.reply_text(f"No member named “{name_tok}” in this chat.")
        return
    _tracker.check_and_reset_budget(member.member_id)
    budget = _tracker.get_or_create_budget(member.member_id)
    usage = _tracker.get_usage(member.member_id, days=30)
    month_tokens = sum(u.tokens for u in usage)
    lines = [
        f"💰 {member.display_name}",
        "",
        budget.to_user_display(),
        "",
        f"Recorded usage (last 30 days): {month_tokens:,} tokens",
        f"Monthly limit: {budget.monthly_limit:,} tokens",
    ]
    if not budget.can_execute():
        lines.append("")
        lines.append(
            f"⚠️ Budget exhausted. Ask an admin: /budget adjust {member.display_name} +50000"
        )
    await update.message.reply_text("\n".join(lines))


async def timesheet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recent per-member token usage (Phase 28 “timesheet”)."""
    if not await _gate(update) or not update.message:
        return
    chat_id = _orch_scope(update)
    raw = (update.message.text or "").strip()
    parts = raw.split()
    if len(parts) >= 2:
        name_tok = _strip_at(parts[1])
        member = _roster.get_member_by_name(name_tok, chat_id)
        if not member:
            await update.message.reply_text(f"No member named “{name_tok}” in this chat.")
            return
        usage = _tracker.get_usage(member.member_id, days=7)
        if not usage:
            await update.message.reply_text(f"No usage recorded for {member.display_name} in the last 7 days.")
            return
        lines = [f"📊 {member.display_name} — last 7 days", ""]
        for rec in usage[:12]:
            lines.append(rec.to_user_display())
        if len(usage) > 12:
            lines.append(f"\n… and {len(usage) - 12} more")
        await update.message.reply_text("\n".join(lines))
        return

    members = _roster.list_members(chat_id)
    if not members:
        await update.message.reply_text("No team members in this chat.")
        return
    all_u = _tracker.get_team_usage([m.member_id for m in members], days=7)
    if not all_u:
        await update.message.reply_text("No team usage recorded in the last 7 days.")
        return
    lines = ["📊 Team — last 7 days", ""]
    for rec in all_u[:18]:
        lines.append(rec.to_user_display())
    if len(all_u) > 18:
        lines.append(f"\n… and {len(all_u) - 18} more")
    await update.message.reply_text("\n".join(lines))


__all__ = ["budget_cmd", "timesheet_cmd"]
