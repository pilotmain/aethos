# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_explainability_final import build_enterprise_explainability_final


def test_enterprise_explainability() -> None:
    out = build_enterprise_explainability_final({"routing_summary": {"fallback_used": True}})
    exp = out["enterprise_explainability_final"]
    assert "fallback" in exp["why_fallback"].lower()
    assert exp["no_logs_required"] is True
