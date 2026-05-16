# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.brain_routing_visibility import build_brain_routing_panel


def test_brain_panel_has_chain() -> None:
    p = build_brain_routing_panel()
    br = p.get("brain_routing") or {}
    assert "fallback_chain" in br
    assert "supported_tasks" in p
