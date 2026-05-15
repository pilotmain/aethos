# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents import agent_events
from app.runtime.runtime_state import load_runtime_state


def test_emit_agent_event_no_crash(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    agent_events.emit_agent_event(st, "loop_started", loop_id="l1", loop_type="runtime_supervisor")
