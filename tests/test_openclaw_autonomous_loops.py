# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_loops import LOOP_TYPES, ensure_loop, mark_loop_recovered
from app.runtime.runtime_state import load_runtime_state


def test_ensure_loop_idempotent_per_type(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    a = ensure_loop(st, "workflow_supervisor", user_id="u1")
    b = ensure_loop(st, "workflow_supervisor", user_id="u1")
    assert a["loop_id"] == b["loop_id"]
    mark_loop_recovered(st, a["loop_id"])
    found = next(
        (x for x in (st.get("autonomous_loops") or []) if isinstance(x, dict) and x.get("loop_id") == a["loop_id"]),
        None,
    )
    assert found and str(found.get("status")) == "running"


def test_loop_types_const() -> None:
    assert "deployment_supervisor" in LOOP_TYPES
