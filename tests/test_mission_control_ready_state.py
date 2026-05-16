# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.mission_control_ready_state import build_mission_control_ready_state


def test_mission_control_ready_state_structure() -> None:
    from app.services.setup.mission_control_ready_state import MC_ENDPOINTS

    out = build_mission_control_ready_state()
    assert "ready" in out
    assert "endpoints" in out
    assert "/api/v1/runtime/startup" in out["endpoints"]
    assert len(out["endpoints"]) >= len(MC_ENDPOINTS) - 2
