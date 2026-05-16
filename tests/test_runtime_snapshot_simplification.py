# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.nexa_next_state import build_execution_snapshot


def test_execution_snapshot_uses_truth_fields(db_session) -> None:
    snap = build_execution_snapshot(db_session, user_id="step11_user")
    assert "runtime_health" in snap
    assert "operator_traces" in snap
    assert "panels" in snap
