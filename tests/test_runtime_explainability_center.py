# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_explainability_center import build_runtime_explainability_center


def test_explainability_center() -> None:
    out = build_runtime_explainability_center({"intelligent_routing": {"advisory_first": True}})
    assert out["explainability_center"]["bounded"] is True
    assert any(e.get("topic") == "routing" for e in out["runtime_decision_explanations"])
