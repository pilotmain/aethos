# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_runtime_event_persists_in_buffer_and_survives_save(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    emit_runtime_event(st, "task_created", task_id="t_evt", user_id="u1", status="queued")
    assert any(
        isinstance(e, dict) and e.get("event") == "task_created" for e in (st.get("runtime_event_buffer") or [])
    )
    save_runtime_state(st)
    st2 = load_runtime_state()
    buf = st2.get("runtime_event_buffer") or []
    assert any(isinstance(e, dict) and e.get("task_id") == "t_evt" for e in buf)
