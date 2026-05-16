# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.deployments import deployment_rollback
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_deployment_then_rollback_preserves_integrity(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_prod", user_id="u1")
    upsert_deployment(
        st,
        "dpl_prod",
        {
            "deployment_id": "dpl_prod",
            "environment_id": "env_prod",
            "user_id": "u1",
            "status": "completed",
            "deployment_stage": "completed",
            "rollback_available": True,
            "task_id": "",
        },
    )
    assert deployment_rollback.start_rollback(st, "dpl_prod", reason="prod_like")
    deployment_rollback.complete_rollback(st, "dpl_prod", success=True)
    save_runtime_state(st)
    inv = validate_runtime_state(load_runtime_state())
    assert inv.get("ok") is True
    row = (load_runtime_state().get("deployment_records") or {}).get("dpl_prod")
    assert row and str((row.get("rollback") or {}).get("status")) == "completed"
