# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.enterprise_operational_maturity import build_enterprise_operational_maturity


def test_enterprise_operational_maturity_posture() -> None:
    out = build_enterprise_operational_maturity({"runtime_readiness_score": 0.9})
    assert "operational_maturity_scores" in out
    assert out["enterprise_operational_posture"].get("overall_posture") in (
        "strong",
        "maturing",
        "developing",
    )
