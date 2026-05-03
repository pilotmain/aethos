"""Format :func:`~app.services.channels.router.route_inbound` results for Telegram."""

from __future__ import annotations

import json
from typing import Any

def telegram_gateway_should_hand_off(gw: dict[str, Any]) -> bool:
    """True when Nexa gateway produced a concrete reply (Phase 35 — chat is always composed)."""
    if gw.get("dev_run") is not None:
        return True
    if gw.get("status") in ("completed", "timeout"):
        return True
    if gw.get("mission") is not None and gw.get("status"):
        return True
    if gw.get("mode") == "chat":
        t = (gw.get("text") or "").strip()
        return bool(t)
    return False


def format_telegram_gateway_reply(gw: dict[str, Any]) -> str:
    if gw.get("mode") == "chat":
        return (gw.get("text") or "").strip()
    st = gw.get("status")
    if st in ("completed", "timeout"):
        title = (gw.get("mission") or {}).get("title") if isinstance(gw.get("mission"), dict) else None
        head = (title or "Mission").strip()[:200]
        verified = gw.get("execution_verified")
        if st == "completed" and verified is False:
            return (
                f"{head}: completed on Nexa’s side, but **execution was not verified** "
                f"(e.g. heartbeat-only or empty agent output — **no hosted deploy/repo fix is implied**). "
                f"Open Mission Control for details."
            )
        return f"{head}: {st}. See Mission Control on the web for full output."
    return json.dumps(gw, default=str, indent=0)[:4000]
