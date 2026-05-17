# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_startup_coordination import (
    OWNERSHIP_STARTUP_STATES,
    build_runtime_startup_integrity,
)


def test_startup_integrity_states() -> None:
    assert "ownership_coordination" in OWNERSHIP_STARTUP_STATES
    blob = build_runtime_startup_integrity({})
    assert blob["runtime_startup_integrity"]["current_state"] in OWNERSHIP_STARTUP_STATES
