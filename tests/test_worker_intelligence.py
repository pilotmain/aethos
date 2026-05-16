# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.intelligent_worker_ecosystem import build_intelligent_worker_ecosystem


def test_worker_intelligence_ecosystem() -> None:
    out = build_intelligent_worker_ecosystem({"worker_accountability": {"reliability": 0.9}})
    assert out["orchestrator_owned"] is True
    assert out["worker_trust_model"]["trust_indicator"] == "high"
