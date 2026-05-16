# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.nexa_next_state import build_execution_snapshot


def test_state_includes_runtime_agents(db_session) -> None:
    snap = build_execution_snapshot(db_session, user_id="dyn_agent_user")
    assert "runtime_agents" in snap
    assert "office" in snap
    assert "runtime_health" in snap
    assert "brain_visibility" in snap
