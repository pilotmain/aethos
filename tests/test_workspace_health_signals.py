# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.enterprise_runtime_visibility import build_enterprise_runtime_panels


def test_workspace_health_panel() -> None:
    panels = build_enterprise_runtime_panels({})
    assert "workspace_health" in panels
    assert "confidence" in panels["workspace_health"]
