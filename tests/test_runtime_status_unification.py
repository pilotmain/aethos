# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_status_unification import build_unified_runtime_status


def test_unified_runtime_status() -> None:
    out = build_unified_runtime_status({"runtime_readiness_score": 0.9})
    assert "readiness_state" in out["runtime_status"]
