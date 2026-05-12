# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Telegram commands for Phase 13 cron (HTTP → API)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.channels.commands.cron_http import cron_list_via_api, cron_remove_via_api, schedule_via_api


async def cron_schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = update.message.text or ""
    chat_id = str(update.effective_chat.id)
    reply = await schedule_via_api(text, chat_id, channel="telegram")
    await update.message.reply_text(reply[:3900])


async def cron_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    reply = await cron_list_via_api()
    await update.message.reply_text(reply[:3900])


async def cron_remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = update.message.text or ""
    reply = await cron_remove_via_api(text)
    await update.message.reply_text(reply[:3900])


__all__ = ["cron_list_cmd", "cron_remove_cmd", "cron_schedule_cmd"]
