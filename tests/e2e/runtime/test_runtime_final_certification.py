# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.enterprise_runtime_final_certification import build_enterprise_runtime_final_certification


def test_runtime_final_certification_e2e() -> None:
    blob = build_enterprise_runtime_final_certification({"launch_stabilized": True})
    assert "enterprise_runtime_fully_certified" in blob
