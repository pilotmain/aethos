# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution import execution_plan
from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.runtime.integrity.runtime_cleanup import cleanup_runtime_state


def test_cleanup_trims_events_and_prunes_orphan_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    st["runtime_event_buffer"] = [{"event_id": str(i), "event": "x", "timestamp": "t"} for i in range(10)]
    root = execution_plan.execution_root(st)
    root.setdefault("memory", {})["ghost"] = {"outputs": []}
    out = cleanup_runtime_state(st, event_buffer_cap=4)
    assert out["events_trimmed"] == 6
    assert "ghost" not in (execution_plan.execution_root(st).get("memory") or {})
    save_runtime_state(st)
