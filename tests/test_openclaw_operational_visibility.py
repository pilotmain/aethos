# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot


def test_snapshot_contains_deployment_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    snap = build_orchestration_runtime_snapshot("user_z")
    assert "deployments" in snap and "environments" in snap
    assert "operational_workflows_tail" in snap and "deployment_scheduler" in snap
