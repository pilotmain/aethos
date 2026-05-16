# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.aethos_differentiation import build_differentiators_summary


def test_marketplace_health_in_differentiators() -> None:
    mh = build_differentiators_summary().get("marketplace_health") or {}
    assert "plugin_health" in mh
