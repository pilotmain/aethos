"""Telegram `/vercel` shortcuts — delegates to allowlisted CLI helpers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.services.infra_cli import vercel_projects_list, vercel_whoami


VERCEL_HELP = """\
▲ **Vercel commands**

`/vercel` or `/vercel help` — this message  
`/vercel projects list` — list projects (CLI on worker)  
`/vercel whoami` — show logged-in account  

Requires **Vercel CLI** on the host that runs the bot (`npm i -g vercel`) and `vercel login`.
"""


async def vercel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    args = [a.strip() for a in (context.args or [])]
    if not args or args[0].lower() in ("help", "-h", "--help"):
        await update.effective_message.reply_text(VERCEL_HELP.strip())
        return

    head = args[0].lower()
    rest = [a.lower() for a in args[1:]]

    if head == "whoami":
        await update.effective_message.reply_text(vercel_whoami()[:9000])
        return

    if head == "projects" and rest[:1] == ["list"]:
        await update.effective_message.reply_text(vercel_projects_list()[:9000])
        return

    if head in ("list", "ls", "projects"):
        await update.effective_message.reply_text(vercel_projects_list()[:9000])
        return

    await update.effective_message.reply_text(
        "Unknown `/vercel` usage.\n\n" + VERCEL_HELP.strip()[:8000]
    )


__all__ = ["VERCEL_HELP", "vercel_command"]
