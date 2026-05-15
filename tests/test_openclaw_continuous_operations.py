# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_loops import ensure_loop
from app.agents.agent_runtime import register_coordination_agent
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_loop_survives_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    register_coordination_agent(st, user_id="u9")
    rec = ensure_loop(st, "environment_supervisor", user_id="u9")
    lid = rec["loop_id"]
    save_runtime_state(st)
    st2 = load_runtime_state()
    ids = [x.get("loop_id") for x in (st2.get("autonomous_loops") or []) if isinstance(x, dict)]
    assert lid in ids
