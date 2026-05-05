"""Telegram commands for Phase 14 browser automation (HTTP → API)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.channels.commands.browser_http import browser_via_api


async def browser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = update.message.text or ""
    reply = await browser_via_api(text)
    await update.message.reply_text(reply[:3900])


__all__ = ["browser_cmd"]
