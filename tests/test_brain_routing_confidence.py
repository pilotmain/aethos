# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.brain_routing_visibility import build_brain_routing_panel
from app.services.mission_control.runtime_confidence import build_brain_routing_confidence
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_brain_panel_has_routing_confidence() -> None:
    panel = build_brain_routing_panel()
    br = panel.get("brain_routing") or {}
    assert "routing_confidence" in br
    assert "fallback_frequency" in br


def test_brain_confidence_from_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    c = build_brain_routing_confidence(truth)
    assert "routing_confidence" in c
    assert "summary" in c
