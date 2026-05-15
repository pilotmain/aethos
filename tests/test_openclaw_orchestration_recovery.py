# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import task_recovery
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_orchestration_boot_marks_running_as_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    t1 = task_registry.put_task(st, {"type": "noop", "state": "running"})
    t2 = task_registry.put_task(st, {"type": "noop", "state": "completed"})
    save_runtime_state(st)
    st2 = load_runtime_state()
    rec = task_recovery.recover_orchestration_on_boot(st2)
    assert rec["count"] == 1
    assert task_registry.get_task(st2, t1)["state"] == "recovering"
    assert task_registry.get_task(st2, t2)["state"] == "completed"
    assert t1 in (st2.get("recovery_queue") or [])
