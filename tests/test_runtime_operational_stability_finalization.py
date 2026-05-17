# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_operational_stability_finalization import build_runtime_operational_stability_finalization


def test_runtime_operational_stability_finalization() -> None:
    blob = build_runtime_operational_stability_finalization({"launch_stabilized": True, "enterprise_runtime_governed": True})
    assert "runtime_operationally_stable" in blob
