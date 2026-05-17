# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_pressure_governance import build_runtime_pressure_governance


def test_runtime_pressure_recovery() -> None:
    blob = build_runtime_pressure_governance({})
    assert blob["runtime_pressure_recovery"]["ready"] is not None
