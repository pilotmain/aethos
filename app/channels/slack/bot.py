"""Slack Bolt app + Socket Mode runner (Phase 12.1)."""

from __future__ import annotations

import asyncio
import logging

from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from app.channels.slack.handlers import register_slack_handlers
from app.core.config import get_settings

_log = logging.getLogger("nexa.channels.slack.bot")


async def run_slack_socket_bot() -> None:
    """Connect one Socket Mode session (blocks until disconnect)."""
    s = get_settings()
    bot = (s.slack_bot_token or "").strip()
    app_tok = (s.slack_app_token or "").strip()
    sig = (s.slack_signing_secret or "").strip()
    if not bot or not app_tok:
        _log.warning("Slack Socket Mode requires SLACK_BOT_TOKEN and SLACK_APP_TOKEN")
        return

    app = AsyncApp(
        token=bot,
        signing_secret=sig if sig else None,
    )
    register_slack_handlers(app)
    handler = AsyncSocketModeHandler(app, app_tok)
    await handler.start_async()


async def run_slack_socket_bot_forever() -> None:
    """Reconnect loop (same pattern as Discord bot)."""
    while True:
        try:
            await run_slack_socket_bot()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _log.warning("slack socket mode stopped (%s); reconnecting in 5s", exc)
            await asyncio.sleep(5)


__all__ = ["run_slack_socket_bot", "run_slack_socket_bot_forever"]
