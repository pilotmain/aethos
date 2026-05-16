# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.worker_ecosystem_evolution import build_worker_ecosystem_health


def test_worker_ecosystem_health() -> None:
    out = build_worker_ecosystem_health({"worker_accountability": {"reliability": 0.85}})
    assert "health_score" in out
    assert out.get("status") in ("healthy", "busy", "review")
