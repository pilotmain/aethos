# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_port_coordination import build_runtime_port_coordination


def test_runtime_recovery_after_stale_ports_payload() -> None:
    blob = build_runtime_port_coordination()
    coord = blob["runtime_port_coordination"]
    assert "needs_recovery" in coord
    assert "auto_coordinate_recommended" in coord
