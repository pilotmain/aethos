# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Discord bot client — optional background task when ``NEXA_DISCORD_*`` is configured (Phase 42)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings

_log = logging.getLogger("channels.discord_bot")


def _resolve_app_user_id(discord_author_id: str) -> str:
    s = get_settings()
    fixed = (getattr(s, "nexa_discord_app_user_id", None) or "").strip()
    if fixed:
        return fixed[:128]
    return f"discord:{discord_author_id}"[:128]


async def run_discord_bot() -> None:
    """Async entry: connect with bot token and reply via :func:`~app.services.channels.router.route_inbound`."""
    try:
        import discord  # noqa: PLC0415 — optional dependency
    except ImportError:
        _log.warning("discord.py not installed; pip install discord.py")
        return

    s = get_settings()
    if not getattr(s, "nexa_discord_enabled", False):
        return
    token = (getattr(s, "nexa_discord_bot_token", None) or "").strip()
    if not token:
        _log.warning("NEXA_DISCORD_ENABLED but NEXA_DISCORD_BOT_TOKEN is empty")
        return

    intents = discord.Intents.default()
    intents.message_content = True  # privileged — enable in Discord Developer Portal

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        _log.info("discord bot logged in as %s", client.user)

    @client.event
    async def on_message(message: Any) -> None:
        if message.author.bot:
            return
        text = (message.content or "").strip()
        if not text:
            return
        uid = _resolve_app_user_id(str(message.author.id))
        from app.core.db import SessionLocal
        from app.services.channels.router import route_inbound

        with SessionLocal() as db:
            out: dict[str, Any] = route_inbound(
                text,
                uid,
                db=db,
                channel="discord",
                metadata={
                    "discord_guild_id": str(message.guild.id) if message.guild else None,
                    "discord_channel_id": str(message.channel.id),
                    "discord_message_id": str(message.id),
                },
            )
        reply = str(out.get("text") or "…")[:1900]
        try:
            await message.channel.send(reply)
        except Exception as exc:
            _log.warning("discord send failed: %s", exc)

    await client.start(token)


async def run_discord_bot_forever() -> None:
    """Restart loop on disconnect (simple resilience)."""
    while True:
        try:
            await run_discord_bot()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("discord bot crashed: %s", exc)
            await asyncio.sleep(10)


__all__ = ["run_discord_bot", "run_discord_bot_forever"]
