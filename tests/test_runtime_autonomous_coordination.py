# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_autonomous_coordination import build_runtime_autonomous_coordination


def test_runtime_autonomous_coordination() -> None:
    blob = build_runtime_autonomous_coordination({"launch_stabilized": True})
    coord = blob["runtime_autonomous_coordination"]
    assert coord["hidden_operator_actions"] is False
    assert coord["runtime_operational_coordination_only"] is True
