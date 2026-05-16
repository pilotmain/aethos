# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.plugin_runtime import safe_load_plugin


def test_unknown_plugin_fails_safe() -> None:
    row = safe_load_plugin("nonexistent-plugin-xyz")
    assert row.get("state") == "failed"
