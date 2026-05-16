# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.plugins.plugin_registry import get_plugin_manifest, list_plugin_manifests


def test_builtin_provider_plugins_registered() -> None:
    manifests = list_plugin_manifests()
    ids = {m["plugin_id"] for m in manifests}
    assert "vercel-provider" in ids
    assert "telegram-channel" in ids


def test_get_plugin_manifest() -> None:
    m = get_plugin_manifest("vercel-provider")
    assert m is not None
    assert "deployments" in (m.get("capabilities") or [])
