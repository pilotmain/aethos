# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments import deployment_rollback
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_operator_rollback_recovery_outcome(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_oc_rb", user_id="oc_u")
    upsert_deployment(
        st,
        "dpl_oc_rb",
        {
            "deployment_id": "dpl_oc_rb",
            "environment_id": "env_oc_rb",
            "user_id": "oc_u",
            "status": "completed",
            "deployment_stage": "completed",
            "rollback_available": True,
            "task_id": "",
        },
    )
    assert deployment_rollback.start_rollback(st, "dpl_oc_rb", reason="operator_outcome")
    deployment_rollback.complete_rollback(st, "dpl_oc_rb", success=True)
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
    row = (load_runtime_state().get("deployment_records") or {}).get("dpl_oc_rb")
    assert row and str(row.get("deployment_stage") or "") == "rolled_back"
