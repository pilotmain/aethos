# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_lifecycle import bootstrap_new_deployment, transition_deployment_stage
from app.deployments.deployment_registry import upsert_deployment
from app.deployments.deployment_stages import transition_allowed
from app.environments import environment_registry
from app.runtime.runtime_state import load_runtime_state


def test_transition_allowed_linear_path() -> None:
    assert transition_allowed("created", "preflight")
    assert transition_allowed("preflight", "queued")
    assert transition_allowed("queued", "building")
    assert transition_allowed("building", "deploying")
    assert transition_allowed("deploying", "verifying")
    assert transition_allowed("verifying", "completed")


def test_bootstrap_sets_stages(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_lc", user_id="u1")
    upsert_deployment(
        st,
        "dpl_lc",
        {
            "deployment_id": "dpl_lc",
            "environment_id": "env_lc",
            "user_id": "u1",
            "status": "running",
            "workflow_id": "w",
            "task_id": "",
        },
    )
    bootstrap_new_deployment(st, "dpl_lc", environment_id="env_lc", user_id="u1", task_id="", plan_id="p1")
    row = (st.get("deployment_records") or {}).get("dpl_lc")
    assert row
    assert str(row.get("deployment_stage")) == "building"
    hist = row.get("stage_history")
    assert isinstance(hist, list) and len(hist) >= 3


def test_invalid_transition_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_x", user_id="u1")
    upsert_deployment(
        st,
        "dpl_x",
        {
            "deployment_id": "dpl_x",
            "environment_id": "env_x",
            "user_id": "u1",
            "deployment_stage": "completed",
            "status": "completed",
        },
    )
    out = transition_deployment_stage(st, "dpl_x", "deploying", reason="bad", sync_status=True)
    assert out and str(out.get("deployment_stage")) == "completed"
