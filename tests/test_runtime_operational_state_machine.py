# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_operational_state_machine import OPERATIONAL_STATES, build_runtime_operational_state_machine


def test_operational_state_machine() -> None:
    out = build_runtime_operational_state_machine({"runtime_readiness_score": 0.9})
    state = out["runtime_operational_state"]["state"]
    assert state in OPERATIONAL_STATES
