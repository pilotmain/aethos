# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_long_horizon import build_runtime_long_horizon


def test_runtime_long_horizon_bounded() -> None:
    out = build_runtime_long_horizon({"runtime_readiness_score": 0.9})
    assert out["bounded"] is True
    assert isinstance(out["operational_eras"], list)
