"""Send outbound Telegram messages (e.g. dev job completion) using the bot token."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_telegram_message(
    chat_id: str,
    text: str,
    *,
    max_len: int = 3900,
    parse_mode: str | None = None,
    reply_markup: dict[str, Any] | None = None,
) -> bool:
    if not (os.getenv("DEV_WORKER_TELEGRAM_NOTIFY", "true").strip().lower() in {"1", "true", "yes", "on"}):
        return False
    if not chat_id or not (text or "").strip():
        return False
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        logger.warning("telegram_outbound: no TELEGRAM_BOT_TOKEN for notify")
        return False
    body: dict[str, Any] = {"chat_id": chat_id, "text": text[:max_len]}
    if parse_mode:
        body["parse_mode"] = parse_mode
    if reply_markup:
        body["reply_markup"] = reply_markup
    try:
        from app.services.safe_http_client import telegram_send_message_post

        r = telegram_send_message_post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json_body=body,
            timeout=20.0,
        )
        if r.status_code != 200:
            logger.warning("telegram sendMessage http=%s body=%s", r.status_code, r.text[:500])
            return False
        return True
    except ValueError as exc:
        logger.warning("telegram_outbound gated: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.exception("telegram sendMessage failed: %s", exc)
        return False
