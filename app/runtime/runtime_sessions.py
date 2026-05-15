# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Session records persisted in ``aethos.json`` (Phase 1 shell — expand with DB later)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso


def append_session_record(session_id: str, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    sessions = st.setdefault("sessions", [])
    if not isinstance(sessions, list):
        sessions = []
        st["sessions"] = sessions
    sessions.append({"id": str(session_id), "last_activity": utc_now_iso(), "meta": dict(meta or {})})
    save_runtime_state(st)
    return st
