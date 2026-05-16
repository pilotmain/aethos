# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


def test_recovery_boot_marks_running_as_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_rec", user_id="u1")
    upsert_deployment(
        st,
        "dpl_rec",
        {
            "deployment_id": "dpl_rec",
            "environment_id": "env_rec",
            "user_id": "u1",
            "status": "running",
            "deployment_stage": "deploying",
            "task_id": "",
        },
    )
    out = recover_deployments_on_boot(st)
    assert int(out.get("deployments_marked_recovering") or 0) >= 1
    row = (st.get("deployment_records") or {}).get("dpl_rec")
    assert row and str(row.get("status") or "") == "recovering"
    assert validate_runtime_state(st).get("ok") is True
