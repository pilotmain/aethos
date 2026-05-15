# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_plan import attach_plan_to_task, create_plan
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_runtime_task_artifacts_endpoint(api_client, tmp_path, monkeypatch) -> None:
    client, uid = api_client
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "workflow", "user_id": uid, "state": "completed"})
    pid = create_plan(
        st,
        tid,
        [
            {
                "step_id": "s1",
                "type": "shell",
                "status": "completed",
                "tool": {"name": "shell", "input": {}},
                "result": {"stdout": "artifact_line", "returncode": 0, "ok": True},
            }
        ],
    )
    attach_plan_to_task(st, tid, pid)
    save_runtime_state(st)

    r = client.get(f"/api/v1/runtime/tasks/{tid}/artifacts")
    assert r.status_code == 200
    data = r.json()
    assert any(a.get("kind") == "stdout" for a in data.get("artifacts") or [])
