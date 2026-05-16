# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_health_model import build_enterprise_operational_health
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_enterprise_health_categories() -> None:
    h = build_enterprise_operational_health(
        {
            "runtime_health": {"status": "healthy"},
            "runtime_confidence": {},
            "enterprise_runtime_panels": {},
            "runtime_recommendations": {"recommendations": []},
            "privacy_posture": {},
            "operational_intelligence": {},
        }
    )
    assert h.get("overall") in ("healthy", "warning", "degraded", "critical", "recovering")
    cats = h.get("categories") or {}
    for key in ("runtime", "provider", "deployment", "automation", "governance", "worker", "workspace"):
        assert key in cats
