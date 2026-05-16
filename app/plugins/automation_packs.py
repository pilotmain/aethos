# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Automation pack metadata exposed by plugins (Phase 3 Step 1)."""

from __future__ import annotations

from typing import Any

from app.plugins.plugin_registry import list_plugin_manifests

_PACK_TYPES = frozenset(
    {
        "deployment",
        "monitoring",
        "workspace_maintenance",
        "provider_diagnostics",
        "repair",
        "project_onboarding",
    }
)


def list_automation_packs() -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for m in list_plugin_manifests():
        pack = m.get("automation_pack")
        if pack or "automation_pack" in (m.get("capabilities") or []):
            packs.append(
                {
                    "plugin_id": m.get("plugin_id"),
                    "pack_type": pack or "custom",
                    "name": m.get("name"),
                    "permissions": m.get("permissions") or [],
                    "verified": m.get("verified"),
                }
            )
    return packs


def get_automation_pack(plugin_id: str) -> dict[str, Any] | None:
    for p in list_automation_packs():
        if p.get("plugin_id") == plugin_id:
            return p
    return None
