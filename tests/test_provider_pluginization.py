# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.plugins.plugin_sandbox import plugin_has_permission


def test_vercel_plugin_permission() -> None:
    assert plugin_has_permission("vercel-provider", "provider.vercel")
