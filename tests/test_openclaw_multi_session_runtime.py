# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.runtime.sessions.session_manager import ensure_session_for_operator


def test_multi_session_distinct_channels(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    s_web = ensure_session_for_operator(st, "same_user", "web")
    s_api = ensure_session_for_operator(st, "same_user", "api")
    assert s_web != s_api
    save_runtime_state(st)
    st2 = load_runtime_state()
    rs = st2.get("runtime_sessions") or {}
    assert isinstance(rs, dict)
    assert len(rs) >= 2
