# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.enterprise_runtime_final_certification import build_enterprise_runtime_final_certification


def test_enterprise_runtime_final_certification() -> None:
    truth = {
        "launch_stabilized": True,
        "runtime_supervision_verified": True,
        "runtime_recovery_certified": True,
        "runtime_ownership_authoritative": True,
        "enterprise_runtime_integrity_verified": True,
        "production_runtime_locked": True,
        "runtime_operator_experience": True,
        "production_cut_certified": True,
    }
    blob = build_enterprise_runtime_final_certification(truth)
    final = blob["enterprise_runtime_final_certification"]
    assert final["phase"] == "phase4_step26"
    assert len(final["categories"]) == 15
