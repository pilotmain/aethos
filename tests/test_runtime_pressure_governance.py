# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_pressure_governance import build_runtime_pressure_governance


def test_runtime_pressure_governance() -> None:
    blob = build_runtime_pressure_governance({})
    assert blob["runtime_pressure_governance"]["office_highest_priority"] is True
    assert "runtime_pressure_health" in blob
