# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.brain_routing_visibility import build_brain_routing_panel


def test_brain_routing_panel_keys() -> None:
    panel = build_brain_routing_panel()
    br = panel.get("brain_routing") or {}
    assert "selected_provider" in br
    assert "privacy_mode" in br
    assert "local_first" in br
