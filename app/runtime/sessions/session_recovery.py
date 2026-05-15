"""Recover session rows after process restart (OpenClaw parity)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import utc_now_iso
from app.runtime.sessions import session_events


def recover_runtime_sessions_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    """
    Mark previously **active** sessions as **recovering** so Mission Control can show resume state.
    """
    rs = st.get("runtime_sessions")
    if not isinstance(rs, dict):
        return {"count": 0, "sessions": []}
    touched: list[str] = []
    for sid, row in list(rs.items()):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") != "active":
            continue
        row["status"] = "recovering"
        row["last_activity_at"] = utc_now_iso()
        touched.append(str(sid))
        session_events.log_session_event(
            "session_recovered",
            session_id=str(sid),
            user_id=str(row.get("user_id") or ""),
            channel=str(row.get("channel") or ""),
        )
    return {"count": len(touched), "session_ids": touched}
