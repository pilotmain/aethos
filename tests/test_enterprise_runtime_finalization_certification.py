# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.enterprise_runtime_finalization_certification import build_enterprise_runtime_finalization_certification


def test_enterprise_runtime_finalization_certification() -> None:
    truth = {
        "launch_stabilized": True,
        "runtime_supervision_verified": True,
        "runtime_recovery_certified": True,
        "runtime_truth_governed": True,
        "enterprise_runtime_trusted": True,
        "runtime_operator_experience": True,
        "production_runtime_finalized": True,
        "enterprise_runtime_governed": True,
        "production_cut_certified": True,
    }
    blob = build_enterprise_runtime_finalization_certification(truth)
    assert blob["enterprise_runtime_finalization_certification"]["phase"] == "phase4_step27"
