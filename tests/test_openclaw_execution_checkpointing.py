# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_checkpoint import get_checkpoint, save_checkpoint
from app.execution.execution_plan import create_plan
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_execution_checkpoint_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    pid = create_plan(st, "t1", [{"step_id": "s1"}])
    save_checkpoint(st, pid, "s1", task_id="t1", outputs=[{"x": 1}])
    save_runtime_state(st)
    st2 = load_runtime_state()
    cp = get_checkpoint(st2, pid, "s1")
    assert cp and cp.get("outputs") == [{"x": 1}]
