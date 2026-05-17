# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_recovery_finalization import build_runtime_recovery_finalization


def test_runtime_recovery_finalization() -> None:
    out = build_runtime_recovery_finalization({})
    assert "recovery_success_rate" in out["runtime_recovery_finalization"]
