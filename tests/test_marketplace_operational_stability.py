# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_confidence import build_marketplace_operational_stability
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_marketplace_stability_trust() -> None:
    truth = build_runtime_truth(user_id=None)
    s = build_marketplace_operational_stability(truth)
    assert s.get("trust") in ("high", "degraded", "low")
    assert "summary" in s
