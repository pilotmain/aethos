# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Supervisor / scheduler fields remain coherent after load (stall-surface continuity)."""

from __future__ import annotations

import pytest

from app.execution import execution_plan
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_execution_supervisor_fields_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "exec", "user_id": "u1", "state": "running"})
    pid = execution_plan.create_plan(st, tid, [{"step_id": "s1", "status": "queued", "type": "noop"}])
    tr = task_registry.get_task(st, tid) or {}
    tr["execution_plan_id"] = pid
    task_registry.put_task(st, tr)
    ex = execution_plan.execution_root(st)
    sup = ex.setdefault("supervisor", {})
    sup["ticks"] = 42
    sup["last_error"] = "simulated_stall_probe"
    save_runtime_state(st)
    st2 = load_runtime_state()
    sup2 = execution_plan.execution_root(st2).get("supervisor") or {}
    assert int(sup2.get("ticks") or 0) == 42
    assert str(sup2.get("last_error") or "") == "simulated_stall_probe"
    assert validate_runtime_state(st2).get("ok") is True
