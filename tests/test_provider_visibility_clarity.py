# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.provider_intelligence_panel import build_provider_intelligence_panel


def test_provider_panel_has_auth_and_workspace() -> None:
    p = build_provider_intelligence_panel()
    assert "auth_status" in p
    assert "workspace" in p
    assert "recent_provider_actions" in p
