# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.plugin_runtime import safe_load_plugin


def test_failed_plugin_does_not_raise() -> None:
    row = safe_load_plugin("nonexistent-plugin-recovery-test")
    assert row.get("state") == "failed"
