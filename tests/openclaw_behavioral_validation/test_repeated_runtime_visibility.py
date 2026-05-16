# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot


def test_repeated_snapshot_continuity_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    for _ in range(8):
        snap = build_orchestration_runtime_snapshot("u_vis")
        assert "reliability" in snap and "continuity" in snap
        assert snap["continuity"].get("restart_recovery_success_rate") is not None
