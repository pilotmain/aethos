# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.worker_ecosystem_optimization import build_adaptive_worker_ecosystem


def test_adaptive_worker_ecosystem() -> None:
    out = build_adaptive_worker_ecosystem({})
    assert out.get("advisory") is True
    assert "worker_optimization_quality" in out
