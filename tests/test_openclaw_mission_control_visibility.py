# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.nexa_next_state import build_execution_snapshot


def test_mission_control_state_includes_runtime_visibility(db_session) -> None:
    snap = build_execution_snapshot(db_session, user_id="mc_vis_user")
    ort = snap.get("orchestration_runtime") or {}
    assert "heartbeat" in ort
    assert "workflows" in ort
    assert "sessions" in ort
    assert "runtime_events_tail" in ort
    assert "tasks" in ort
    pln = ort.get("planning") or {}
    assert "records_tail" in pln
    assert "outcomes_tail" in pln
    assert "reasoning_tail" in pln
    assert "optimization_tail" in pln
    res = ort.get("resilience") or {}
    assert "integrity_ok" in res
    assert "backup_files_on_disk" in res
