"""High-level session selection for operators (multi-session parity)."""

from __future__ import annotations

from typing import Any

from app.runtime.sessions import session_channels
from app.runtime.sessions import session_registry


def ensure_session_for_operator(st: dict[str, Any], user_id: str, channel: str | None = None) -> str:
    """
    Return an **active** session id for ``user_id`` + normalized channel, reusing when possible.
    """
    uid = str(user_id or "").strip() or "unknown"
    ch = session_channels.normalize_channel(channel)
    for sid, row in (st.get("runtime_sessions") or {}).items():
        if not isinstance(row, dict):
            continue
        if str(row.get("user_id") or "") != uid:
            continue
        if str(row.get("channel") or "") != ch:
            continue
        if str(row.get("status") or "active") not in ("active", "recovering"):
            continue
        session_registry.touch_session(st, str(sid))
        return str(sid)
    return session_registry.create_session(st, user_id=uid, channel=ch)
