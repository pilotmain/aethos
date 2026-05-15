"""Persistent ``runtime_sessions`` map in ``aethos.json``."""

from __future__ import annotations

import uuid
from typing import Any

from app.runtime.runtime_state import utc_now_iso
from app.runtime.sessions import session_channels


def _sessions(st: dict[str, Any]) -> dict[str, Any]:
    rs = st.setdefault("runtime_sessions", {})
    if not isinstance(rs, dict):
        st["runtime_sessions"] = {}
        return st["runtime_sessions"]
    return rs


def upsert_session(st: dict[str, Any], row: dict[str, Any]) -> str:
    sid = str(row.get("session_id") or uuid.uuid4())
    row = dict(row)
    row["session_id"] = sid
    row.setdefault("created_at", utc_now_iso())
    row["last_activity_at"] = utc_now_iso()
    _sessions(st)[sid] = row
    return sid


def get_session(st: dict[str, Any], session_id: str) -> dict[str, Any] | None:
    s = _sessions(st).get(str(session_id))
    return dict(s) if isinstance(s, dict) else None


def list_sessions_for_user(st: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    out: list[dict[str, Any]] = []
    for sid, row in _sessions(st).items():
        if not isinstance(row, dict):
            continue
        if str(row.get("user_id") or "") != uid:
            continue
        out.append(dict(row, session_id=str(sid)))
    out.sort(key=lambda r: str(r.get("last_activity_at") or ""), reverse=True)
    return out


def create_session(
    st: dict[str, Any],
    *,
    user_id: str,
    channel: str,
    agent_id: str | None = None,
) -> str:
    ch = session_channels.normalize_channel(channel)
    sid = str(uuid.uuid4())
    row: dict[str, Any] = {
        "session_id": sid,
        "user_id": str(user_id or "").strip(),
        "channel": ch,
        "created_at": utc_now_iso(),
        "last_activity_at": utc_now_iso(),
        "active_tasks": [],
        "active_agents": [agent_id] if agent_id else [],
        "status": "active",
        "runtime_state": {},
    }
    _sessions(st)[sid] = row
    from app.runtime.sessions import session_events

    session_events.log_session_event("session_created", session_id=sid, user_id=row["user_id"], channel=ch)
    return sid


def touch_session(st: dict[str, Any], session_id: str) -> None:
    row = _sessions(st).get(str(session_id))
    if isinstance(row, dict):
        row["last_activity_at"] = utc_now_iso()


def attach_task(st: dict[str, Any], session_id: str, task_id: str) -> None:
    row = _sessions(st).get(str(session_id))
    if not isinstance(row, dict):
        return
    at = [str(x) for x in (row.get("active_tasks") or []) if x is not None]
    tid = str(task_id)
    if tid not in at:
        at.append(tid)
    row["active_tasks"] = at
    row["last_activity_at"] = utc_now_iso()


def detach_task(st: dict[str, Any], session_id: str, task_id: str) -> None:
    row = _sessions(st).get(str(session_id))
    if not isinstance(row, dict):
        return
    tid = str(task_id)
    at = [str(x) for x in (row.get("active_tasks") or []) if str(x) != tid]
    row["active_tasks"] = at
    row["last_activity_at"] = utc_now_iso()
