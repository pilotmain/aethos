# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.enterprise_operational_command_authority import build_enterprise_operational_command_authority


def test_enterprise_operational_command_authority() -> None:
    blob = build_enterprise_operational_command_authority({"launch_stabilized": True})
    assert blob["enterprise_operational_command_authority"]["phase"] == "phase4_step27"
