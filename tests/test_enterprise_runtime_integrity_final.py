# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.enterprise_runtime_integrity_final import build_enterprise_runtime_integrity_final


def test_enterprise_runtime_integrity_final() -> None:
    truth = {"launch_stabilized": True, "runtime_supervision_verified": True}
    blob = build_enterprise_runtime_integrity_final(truth)
    final = blob["enterprise_runtime_integrity_final"]
    assert final["phase"] == "phase4_step25"
    assert "enterprise_runtime_integrity_verified" in final
    assert len(final["categories"]) == 11
