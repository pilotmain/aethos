# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Telegram — ClawHub marketplace commands (Phase 71).

Commands:
    /skills_search <query>             — search the configured ClawHub registry
    /skills_popular                    — list popular skills on ClawHub
    /skills_list                       — list installed marketplace skills
    /skills_install <name> [version]   — install a skill (owner-only, default version=latest)
    /skills_uninstall <name>           — remove an installed skill (owner-only)
    /skills_update <name>              — re-fetch + reinstall if a newer version exists (owner-only)

Wire-up: :func:`app.services.channel_gateway.telegram_adapter.register_telegram_handlers`.

Mutating commands require the Telegram-linked **owner** role (same gate the web
``/api/v1/marketplace/{install,uninstall,update}`` proxies use). Read-only
commands are available to any non-blocked Telegram user, gated by
``NEXA_CLAWHUB_ENABLED`` (the underlying client returns empty results when the
flag is off, so the handler reports a friendly message).
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.skills.clawhub_client import ClawHubClient
from app.services.skills.installer import SkillInstaller
from app.services.user_capabilities import (
    BLOCKED_MSG,
    get_telegram_role,
    is_owner_role,
)


def _clawhub_disabled_message() -> str | None:
    s = get_settings()
    if not bool(getattr(s, "nexa_clawhub_enabled", True)):
        return "ClawHub marketplace is disabled (NEXA_CLAWHUB_ENABLED=false)."
    return None


async def _gate(update: Update, *, require_owner: bool) -> bool:
    if not update.effective_user or not update.message:
        return False
    disabled = _clawhub_disabled_message()
    if disabled:
        await update.message.reply_text(disabled)
        return False
    db = SessionLocal()
    try:
        role = get_telegram_role(update.effective_user.id, db)
    finally:
        db.close()
    if role == "blocked":
        await update.message.reply_text(BLOCKED_MSG)
        return False
    if require_owner and not is_owner_role(role):
        await update.message.reply_text(
            "Only the workspace owner can install / uninstall / update marketplace skills."
        )
        return False
    return True


def _format_search_row(sk) -> str:  # type: ignore[no-untyped-def]
    desc = (sk.description or "").strip()
    if len(desc) > 80:
        desc = desc[:77] + "…"
    pub = sk.publisher or "community"
    return f"• {sk.name} v{sk.version} — {desc} ({pub})"


async def skills_search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update, require_owner=False) or not update.message:
        return
    query = " ".join(context.args or []).strip()
    if not query:
        await update.message.reply_text("Usage: /skills_search <query>")
        return
    rows = await ClawHubClient().search_skills(query, limit=10)
    if not rows:
        await update.message.reply_text(
            f"No marketplace skills matched '{query}' (or the registry is unreachable)."
        )
        return
    lines = [f"Marketplace results for '{query}':"]
    lines.extend(_format_search_row(r) for r in rows)
    lines.append("")
    lines.append("Install with /skills_install <name> (owner only).")
    await update.message.reply_text("\n".join(lines))


async def skills_popular_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    if not await _gate(update, require_owner=False) or not update.message:
        return
    rows = await ClawHubClient().list_popular(limit=10)
    if not rows:
        await update.message.reply_text(
            "Popular list empty (the configured ClawHub registry returned nothing)."
        )
        return
    lines = ["Popular skills on ClawHub:"]
    for r in rows:
        lines.append(
            f"• {r.name} v{r.version} — ★ {r.rating:.1f} · {r.downloads:,} downloads"
        )
    await update.message.reply_text("\n".join(lines))


async def skills_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    if not await _gate(update, require_owner=False) or not update.message:
        return
    skills = SkillInstaller().list_installed()
    if not skills:
        await update.message.reply_text(
            "No marketplace skills installed. Use /skills_search <query> to discover one."
        )
        return
    lines = ["Installed marketplace skills:"]
    for s in skills:
        lines.append(
            f"• {s.name} v{s.version} ({s.source.value}) — {s.status.value}"
        )
    await update.message.reply_text("\n".join(lines))


async def skills_install_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update, require_owner=True) or not update.message:
        return
    args = list(context.args or [])
    if not args:
        await update.message.reply_text(
            "Usage: /skills_install <name> [version]   (default version=latest)"
        )
        return
    name = args[0].strip()
    version = (args[1].strip() if len(args) > 1 else "latest") or "latest"
    ok, msg, key = await SkillInstaller().install(name, version, force=False)
    if ok:
        await update.message.reply_text(
            f"Installed {key or name} ({msg}). Use /skills_list to verify."
        )
        return
    await update.message.reply_text(f"Install failed for {name}: {msg}")


async def skills_uninstall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update, require_owner=True) or not update.message:
        return
    args = list(context.args or [])
    if not args:
        await update.message.reply_text("Usage: /skills_uninstall <name>")
        return
    name = args[0].strip()
    ok, msg = await SkillInstaller().uninstall(name)
    if ok:
        await update.message.reply_text(f"Uninstalled {name}.")
        return
    await update.message.reply_text(f"Uninstall failed for {name}: {msg}")


async def skills_update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update, require_owner=True) or not update.message:
        return
    args = list(context.args or [])
    if not args:
        await update.message.reply_text("Usage: /skills_update <name>")
        return
    name = args[0].strip()
    ok, msg = await SkillInstaller().update(name, force=False)
    if ok:
        await update.message.reply_text(f"{name}: {msg}")
        return
    await update.message.reply_text(f"Update failed for {name}: {msg}")


__all__ = [
    "skills_install_cmd",
    "skills_list_cmd",
    "skills_popular_cmd",
    "skills_search_cmd",
    "skills_uninstall_cmd",
    "skills_update_cmd",
]
