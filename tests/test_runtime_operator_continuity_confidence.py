# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_operator_continuity_confidence import build_runtime_operator_continuity_confidence


def test_continuity_confidence() -> None:
    out = build_runtime_operator_continuity_confidence(
        {"runtime_continuity_certification": {"certified": True}, "runtime_recovery_integrity": {"stable": True}}
    )
    assert "continuity" in out["runtime_operator_continuity_confidence"]["summary"].lower()
