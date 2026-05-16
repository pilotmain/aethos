# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.marketplace.runtime_marketplace import marketplace_summary


def test_marketplace_health_plugin_panel() -> None:
    s = marketplace_summary()
    ph = s.get("plugin_health") or {}
    assert "healthy_count" in ph
