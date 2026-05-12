# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Telegram commands for Phase 22 social automation."""

from __future__ import annotations

import json

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.social.orchestrator import SocialOrchestrator, SocialPlatform
from app.services.user_capabilities import BLOCKED_MSG, get_telegram_role


async def tweet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    s = get_settings()
    if not (s.nexa_social_enabled and s.nexa_twitter_enabled):
        await update.message.reply_text(
            "Social Twitter is off (set NEXA_SOCIAL_ENABLED and NEXA_TWITTER_ENABLED, plus Twitter OAuth1 keys)."
        )
        return
    db = SessionLocal()
    try:
        if get_telegram_role(update.effective_user.id, db) == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
    finally:
        db.close()

    text = " ".join(context.args or []).strip()
    if not text:
        await update.message.reply_text("Usage: /tweet <message>")
        return

    orch = SocialOrchestrator()
    out = await orch.post(SocialPlatform.TWITTER, text)
    if not out.get("ok"):
        await update.message.reply_text(json.dumps(out, indent=2)[:3900])
        return
    await update.message.reply_text("Posted to Twitter/X.")


async def search_tweets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    s = get_settings()
    if not (s.nexa_social_enabled and s.nexa_twitter_enabled):
        await update.message.reply_text(
            "Social Twitter is off (set NEXA_SOCIAL_ENABLED, NEXA_TWITTER_ENABLED, TWITTER_BEARER_TOKEN)."
        )
        return
    db = SessionLocal()
    try:
        if get_telegram_role(update.effective_user.id, db) == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
    finally:
        db.close()

    q = " ".join(context.args or "").strip()
    if not q:
        await update.message.reply_text("Usage: /search_tweets <query>")
        return

    orch = SocialOrchestrator()
    rows = await orch.search(SocialPlatform.TWITTER, q, limit=5)
    if not rows:
        await update.message.reply_text("No results (check bearer token / API tier).")
        return
    lines = []
    for i, t in enumerate(rows[:5], 1):
        tid = t.get("id") or ""
        txt = (t.get("text") or "")[:280]
        lines.append(f"{i}. [{tid}] {txt}")
    await update.message.reply_text("\n".join(lines)[:3900])


__all__ = ["search_tweets_cmd", "tweet_cmd"]
