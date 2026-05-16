# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.mission_control.runtime_resilience import build_execution_snapshot_resilient


def test_execution_snapshot_resilient_degraded() -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("hydration failed")

    out = build_execution_snapshot_resilient(
        MagicMock(),
        user_id="u1",
        hours=24,
        builder=_boom,
    )
    assert out["operational_status"] == "degraded"
    assert "runtime_resilience" in out
