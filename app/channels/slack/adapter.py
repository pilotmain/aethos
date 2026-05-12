# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""``NexaChannel`` binding for Slack Socket Mode."""

from __future__ import annotations

import asyncio
from typing import Any

from app.channels.base import ChannelMessage, ChannelResponse, NexaChannel
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.channel_gateway.slack_api import slack_chat_post_message
from app.services.channels.router import route_inbound


class SlackSocketNexaChannel(NexaChannel):
    """Slack transport using Bolt Socket Mode (started from FastAPI lifespan)."""

    name = "slack"

    @property
    def enabled(self) -> bool:
        s = get_settings()
        return bool(
            getattr(s, "nexa_slack_enabled", False)
            and (s.slack_bot_token or "").strip()
            and (s.slack_app_token or "").strip()
        )

    async def start(self) -> None:
        from app.channels.slack.bot import run_slack_socket_bot_forever

        await run_slack_socket_bot_forever()

    async def send_message(self, channel_id: str, text: str) -> None:
        tok = (get_settings().slack_bot_token or "").strip()
        if not tok:
            raise RuntimeError("SLACK_BOT_TOKEN is not set")

        def _send() -> dict[str, Any]:
            return slack_chat_post_message(
                tok,
                channel=channel_id,
                text=text[:39000],
                thread_ts=None,
                blocks=None,
                rate_limit_user_id=None,
            )

        await asyncio.to_thread(_send)

    async def handle_message(self, message: ChannelMessage) -> ChannelResponse:
        db = SessionLocal()
        try:
            raw = route_inbound(
                message.text,
                message.user_id,
                db=db,
                channel="slack",
                metadata=message.metadata,
            )
            return ChannelResponse(
                text=str(raw.get("text") or ""),
                metadata={"intent": raw.get("intent")},
            )
        finally:
            db.close()


__all__ = ["SlackSocketNexaChannel"]
