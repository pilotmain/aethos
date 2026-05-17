# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_hydration_diagnostics import build_runtime_hydration_diagnostics


def test_hydration_diagnostics() -> None:
    out = build_runtime_hydration_diagnostics({})
    assert "runtime_hydration_diagnostics" in out
    assert "slice_durations_ms" in out["runtime_hydration_diagnostics"]
