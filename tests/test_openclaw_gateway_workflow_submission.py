# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution import execution_plan
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_gateway_workflow_submission(api_client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    client, uid = api_client
    r = client.post(
        "/api/v1/mission-control/gateway/run",
        json={"text": "echo gateway_wf_ok", "user_id": uid, "workflow": True},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("mode") == "workflow"
    tid = data.get("task_id")
    assert tid
    st = load_runtime_state()
    for _ in range(30):
        runtime_dispatcher.dispatch_once(st)
        save_runtime_state(st)
        t = task_registry.get_task(st, str(tid))
        if t and str(t.get("state") or "") in ("completed", "failed"):
            break
    st2 = load_runtime_state()
    t2 = task_registry.get_task(st2, str(tid))
    assert t2 and t2.get("state") == "completed"
    pid = str(t2.get("execution_plan_id") or "")
    plan = execution_plan.get_plan(st2, pid)
    rc = (plan["steps"][0].get("result") or {}).get("returncode")
    assert rc == 0
