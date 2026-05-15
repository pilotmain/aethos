# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.environments import environment_health
from app.environments import environment_registry
from app.runtime.runtime_state import load_runtime_state


def test_note_deployment_outcome_updates_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    eid = environment_registry.default_environment_id_for_user(st, "bob")
    environment_health.note_deployment_outcome(st, eid, success=False)
    row = environment_registry.get_environment(st, eid)
    assert row and row.get("status") == "degraded"
