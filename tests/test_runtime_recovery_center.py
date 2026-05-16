# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_recovery_center import build_runtime_recovery_center


def test_recovery_center_recommendations() -> None:
    out = build_runtime_recovery_center(
        {
            "runtime_resilience": {"status": "degraded"},
            "operational_recovery_state": {"degradation_signals": [{"kind": "x"}]},
        }
    )
    assert out["operational_status"] in ("degraded", "recovering")
    assert isinstance(out["recovery_recommendations"], list)
