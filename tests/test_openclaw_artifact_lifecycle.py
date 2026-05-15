# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.main import app
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from fastapi.testclient import TestClient


def test_file_write_workflow_artifact_visible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "write file parity_lc.txt artifact_body", user_id="art_u")
    save_runtime_state(st)
    tid = out["task_id"]
    st2 = load_runtime_state()
    for _ in range(25):
        runtime_dispatcher.dispatch_once(st2)
        save_runtime_state(st2)
        t = task_registry.get_task(st2, tid)
        if t and str(t.get("state") or "") in ("completed", "failed"):
            break
    client = TestClient(app)
    from app.core.security import get_valid_web_user_id

    client.app.dependency_overrides[get_valid_web_user_id] = lambda: "art_u"
    try:
        r = client.get(f"/api/v1/runtime/tasks/{tid}/artifacts")
        assert r.status_code == 200
        arts = r.json().get("artifacts") or []
        assert any("parity_lc.txt" in str(a) for a in arts)
    finally:
        client.app.dependency_overrides.clear()
