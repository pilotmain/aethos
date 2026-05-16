# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.plugin_runtime import build_plugin_health_panel, safe_load_plugin


def test_plugin_health_panel_shape() -> None:
    panel = build_plugin_health_panel()
    assert "warnings" in panel
    assert "failures" in panel
    assert "healthy_count" in panel


def test_unknown_plugin_isolated() -> None:
    row = safe_load_plugin("missing-plugin-id")
    assert row.get("state") == "failed"
