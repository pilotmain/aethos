# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.brain_routing_visibility import build_brain_routing_panel


def test_routing_confidence_exposed() -> None:
    br = (build_brain_routing_panel().get("brain_routing") or {})
    assert "routing_confidence" in br
    assert "fallback_chain" in br
    assert "reason" in br
