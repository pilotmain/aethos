# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.plugin_registry import get_plugin_manifest


def test_vercel_official_tier() -> None:
    m = get_plugin_manifest("vercel-provider")
    assert m is not None
    assert m.get("trust_tier") == "official"
    assert m.get("verified") is True
