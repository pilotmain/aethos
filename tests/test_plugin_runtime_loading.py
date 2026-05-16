# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.plugin_runtime import disable_plugin, load_plugin


def test_load_and_disable_vercel() -> None:
    row = load_plugin("vercel-provider")
    assert row.get("state") in ("active", "loaded")
    disabled = disable_plugin("vercel-provider")
    assert disabled.get("state") == "disabled"
