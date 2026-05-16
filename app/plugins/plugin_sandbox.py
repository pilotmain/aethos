# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin permission checks (Phase 2 Step 8)."""

from __future__ import annotations

from app.plugins.plugin_registry import get_plugin_manifest


def plugin_has_permission(plugin_id: str, permission: str) -> bool:
    m = get_plugin_manifest(plugin_id)
    if not m:
        return False
    perms = m.get("permissions") or []
    return permission in perms or f"provider.{plugin_id}" in perms
