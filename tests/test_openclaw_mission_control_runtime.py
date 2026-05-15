# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.nexa_next_state import build_execution_snapshot


def test_mission_control_snapshot_includes_orchestration_runtime(db_session) -> None:
    snap = build_execution_snapshot(db_session, user_id="mc_rt_user")
    assert "orchestration_runtime" in snap
    ort = snap["orchestration_runtime"]
    assert "heartbeat" in ort
    assert "queues" in ort
    assert "metrics" in ort
    assert "sessions" in ort
    pln = ort.get("planning") or {}
    assert isinstance(pln, dict)
    assert "records_tail" in pln
    assert "outcomes_tail" in pln
