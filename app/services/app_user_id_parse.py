"""Lightweight app user id parsing — keep free of web_chat_service to avoid import cycles."""

from __future__ import annotations

import re


def parse_telegram_id_from_app_user_id(app_user_id: str) -> int | None:
    m = re.match(r"^tg_(\d+)$", (app_user_id or "").strip())
    if not m:
        return None
    return int(m.group(1))
