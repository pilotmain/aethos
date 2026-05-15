# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.runtime.sessions.session_manager import ensure_session_for_operator
from app.runtime.sessions.session_registry import create_session, get_session
from app.runtime.sessions.session_recovery import recover_runtime_sessions_on_boot


def test_session_boot_marks_active_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    sid = create_session(st, user_id="u_boot", channel="web")
    out = recover_runtime_sessions_on_boot(st)
    assert out.get("count") == 1
    assert get_session(st, sid).get("status") == "recovering"


def test_runtime_session_persist_and_reload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    sid = ensure_session_for_operator(st, "user_a", "web")
    save_runtime_state(st)
    st2 = load_runtime_state()
    row = get_session(st2, sid)
    assert row and row.get("user_id") == "user_a"
    assert row.get("channel") == "web"
