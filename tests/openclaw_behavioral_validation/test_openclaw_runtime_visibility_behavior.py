# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot


def test_snapshot_exposes_reliability_and_resilience(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    snap = build_orchestration_runtime_snapshot(None)
    assert "reliability" in snap and "resilience" in snap
    assert snap["reliability"].get("severity")
