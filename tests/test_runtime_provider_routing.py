# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_provider_routing import build_runtime_provider_routing


def test_runtime_provider_routing_advisory() -> None:
    out = build_runtime_provider_routing({"routing_summary": {"fallback_used": True, "reason": "test"}})
    assert out["adaptive_provider_routing"]["orchestrator_controlled"] is True
    assert out["routing_decision_explanations"]
