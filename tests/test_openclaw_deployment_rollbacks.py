# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments import deployment_rollback
from app.deployments.deployment_registry import upsert_deployment
from app.runtime.runtime_state import load_runtime_state


def test_rollback_start_and_complete(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    upsert_deployment(
        st,
        "dpl_rb",
        {
            "deployment_id": "dpl_rb",
            "environment_id": "env_rb",
            "status": "completed",
            "user_id": "u1",
            "rollback_available": True,
            "workflow_id": "w",
            "task_id": "t",
        },
    )
    assert deployment_rollback.start_rollback(st, "dpl_rb", reason="test")
    deployment_rollback.complete_rollback(st, "dpl_rb", success=True)
    row = (st.get("deployment_records") or {}).get("dpl_rb")
    assert row and str((row.get("rollback") or {}).get("status")) == "completed"
