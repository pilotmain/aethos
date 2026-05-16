# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.provider_intelligence_panel import build_provider_intelligence_panel


def test_provider_intelligence_shape() -> None:
    p = build_provider_intelligence_panel()
    assert "provider_inventory" in p
    assert "workspace" in p
