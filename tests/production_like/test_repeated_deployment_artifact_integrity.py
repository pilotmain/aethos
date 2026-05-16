# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.deployments.deployment_lifecycle import bootstrap_new_deployment, transition_deployment_stage
from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_repeated_deployments_preserve_artifacts_and_diagnostics(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = 28 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 12
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_art", user_id="u1")
    marker = {"bundle": "parity-freeze", "checksum": "abc123"}
    for i in range(n):
        did = f"dpl_art_{i}"
        bootstrap_new_deployment(st, did, environment_id="env_art", user_id="u1", task_id="", plan_id=f"plan_{i}")
        row = get_deployment(st, did)
        assert row
        arts = [{"kind": "bundle", "ref": f"ref_{i}", "meta": marker}]
        upsert_deployment(
            st,
            did,
            {
                "artifacts": arts,
                "deployment_diagnostics": {"pass": True, "cycle": i, "marker": marker},
            },
        )
        for s in ("deploying", "verifying", "completed"):
            transition_deployment_stage(st, did, s, reason="artifact_integrity", sync_status=True)
        row2 = get_deployment(st, did)
        assert row2 and isinstance(row2.get("deployment_diagnostics"), dict)
        assert row2["deployment_diagnostics"].get("marker") == marker
        a = row2.get("artifacts")
        assert isinstance(a, list) and len(a) >= 1
        cps = row2.get("checkpoints")
        assert isinstance(cps, list) and len(cps) <= 120
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
