# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority


def test_runtime_governance_authority() -> None:
    blob = build_runtime_governance_authority({"launch_stabilized": True})
    assert blob["runtime_governance_authority"]["phase"] == "phase4_step26"
    assert "enterprise_runtime_governance" in blob
