# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.plugin_registry import get_plugin_manifest


def test_marketplace_fields() -> None:
    m = get_plugin_manifest("vercel-provider")
    assert m is not None
    assert "author" in m
    assert "verified" in m
    assert "installed" in m
