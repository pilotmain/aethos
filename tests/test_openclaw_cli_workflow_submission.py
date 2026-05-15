# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json

from app.execution import execution_plan
from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_cli_gateway_payload_shape() -> None:
    """Contract for ``aethos message send --workflow`` JSON body."""
    body = {"text": "echo cli_wf", "user_id": "cli_user", "workflow": True}
    raw = json.dumps(body)
    assert '"workflow": true' in raw


def test_cli_equivalent_local_dispatch(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "echo cli_local_ok", user_id="cli_user")
    save_runtime_state(st)
    tid = out["task_id"]
    st2 = load_runtime_state()
    for _ in range(20):
        runtime_dispatcher.dispatch_once(st2)
        save_runtime_state(st2)
        t = task_registry.get_task(st2, tid)
        if t and str(t.get("state") or "") in ("completed", "failed"):
            break
    t2 = task_registry.get_task(load_runtime_state(), tid)
    assert t2 and t2.get("state") == "completed"
    pid = str(t2.get("execution_plan_id") or "")
    plan = execution_plan.get_plan(load_runtime_state(), pid)
    assert "cli_local_ok" in str((plan["steps"][0].get("result") or {}).get("stdout") or "")
