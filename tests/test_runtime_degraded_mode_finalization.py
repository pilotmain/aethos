# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_degraded_mode_finalization import build_runtime_degraded_mode_finalization


def test_degraded_mode_calm() -> None:
    out = build_runtime_degraded_mode_finalization({"hydration_progress": {"partial": True}})
    assert "synchronizing" in out["runtime_degraded_mode_finalization"]["operator_headline"].lower()
