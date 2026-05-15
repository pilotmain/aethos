"""Helpers for filtering runtime events by session (streaming parity)."""

from __future__ import annotations

from typing import Any


def events_for_session(events: list[dict[str, Any]], session_id: str) -> list[dict[str, Any]]:
    sid = str(session_id or "").strip()
    if not sid:
        return []
    out: list[dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("session_id") or "") == sid:
            out.append(ev)
    return out
