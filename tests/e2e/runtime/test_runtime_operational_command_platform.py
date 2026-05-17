# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.enterprise_runtime_finalization_certification import build_enterprise_runtime_finalization_certification


def test_runtime_operational_command_platform() -> None:
    blob = build_enterprise_runtime_finalization_certification({"launch_stabilized": True})
    assert "enterprise_operational_command_locked" in blob
