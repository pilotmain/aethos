"""Format :func:`~app.services.channels.router.route_inbound` results for Telegram."""

from __future__ import annotations

import json
from typing import Any

from app.services.gateway.runtime import GATEWAY_CHAT_FALLBACK_TEXT


def telegram_gateway_should_hand_off(gw: dict[str, Any]) -> bool:
    """True when Nexa gateway produced a concrete reply (not the generic chat fallback)."""
    if gw.get("dev_run") is not None:
        return True
    if gw.get("status") in ("completed", "timeout"):
        return True
    if gw.get("mission") is not None and gw.get("status"):
        return True
    if gw.get("mode") == "chat":
        t = (gw.get("text") or "").strip()
        return bool(t) and t != GATEWAY_CHAT_FALLBACK_TEXT
    return False


def format_telegram_gateway_reply(gw: dict[str, Any]) -> str:
    if gw.get("mode") == "chat":
        return (gw.get("text") or "").strip()
    st = gw.get("status")
    if st in ("completed", "timeout"):
        title = (gw.get("mission") or {}).get("title") if isinstance(gw.get("mission"), dict) else None
        head = (title or "Mission").strip()[:200]
        return f"{head}: {st}. See Mission Control on the web for full output."
    return json.dumps(gw, default=str, indent=0)[:4000]
