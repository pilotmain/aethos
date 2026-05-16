# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.marketplace.runtime_marketplace import get_marketplace_plugin, marketplace_summary


def test_marketplace_summary_stable() -> None:
    s = marketplace_summary()
    assert "installed_count" in s
    assert "plugin_health" in s


def test_unknown_plugin_none() -> None:
    assert get_marketplace_plugin("not-a-real-plugin-id-xyz") is None
