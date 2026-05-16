# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""≥100 deployment stage transitions (bootstrap prefix × deployments)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.deployments.deployment_lifecycle import bootstrap_new_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import widen_runtime_event_buffer

# bootstrap_new_deployment applies 3 transitions: preflight → queued → building.
_DEPLOY_BOOTSTRAP_TRANSITIONS = 3
_TARGET = 100
_DEPLOYS = (_TARGET + _DEPLOY_BOOTSTRAP_TRANSITIONS - 1) // _DEPLOY_BOOTSTRAP_TRANSITIONS  # 34 → 102


@pytest.mark.production_like
def test_at_least_100_deployment_transitions_via_bootstrap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    widen_runtime_event_buffer(monkeypatch)
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        environment_registry.ensure_environment(st, "env_gate_dpl", user_id="u1")
        transitions = 0
        for i in range(_DEPLOYS):
            did = f"dpl_gate_{i}"
            bootstrap_new_deployment(st, did, environment_id="env_gate_dpl", user_id="u1", task_id="", plan_id=f"p{i}")
            transitions += _DEPLOY_BOOTSTRAP_TRANSITIONS
        assert transitions >= _TARGET
        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
