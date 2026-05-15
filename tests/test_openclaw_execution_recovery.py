# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_continuation import recover_execution_on_boot
from app.execution.execution_plan import create_plan, get_plan
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_execution_boot_resets_running_steps(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    pid = create_plan(st, "t1", [{"step_id": "s1"}])
    p = get_plan(st, pid)
    assert p
    p["steps"][0]["status"] = "running"
    save_runtime_state(st)
    st2 = load_runtime_state()
    recover_execution_on_boot(st2)
    assert st2["execution"]["plans"][pid]["steps"][0]["status"] == "queued"
