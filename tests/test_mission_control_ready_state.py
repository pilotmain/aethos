# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.mission_control_ready_state import build_mission_control_ready_state


def test_mission_control_ready_state_shape() -> None:
    out = build_mission_control_ready_state()
    assert "ready" in out
    assert "checks" in out
    assert "endpoints" in out
