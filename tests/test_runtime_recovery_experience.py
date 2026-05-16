# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_recovery_experience import build_runtime_recovery_experience


def test_runtime_recovery_experience_degraded_copy() -> None:
    out = build_runtime_recovery_experience({"runtime_resilience": {"status": "degraded"}})
    headline = out["runtime_recovery_experience"]["headline"]
    assert "reconnecting" in headline.lower()
    assert out["runtime_recovery_experience"]["what_remains_available"]
