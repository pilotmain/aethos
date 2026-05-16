# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Load plugins into the runtime host (Phase 2 Step 8)."""

from __future__ import annotations

from typing import Any

from app.plugins.plugin_events import emit_plugin_event
from app.plugins.plugin_registry import list_plugin_manifests, register_manifest
from app.plugins.plugin_runtime import PluginRuntime
from app.services.plugins.registry import load_plugins as load_tool_plugins


def load_all_plugins() -> dict[str, Any]:
    """Idempotent plugin bootstrap for API process."""
    manifests = list_plugin_manifests()
    runtime = PluginRuntime()
    tool_plugins = load_tool_plugins()
    try:
        import app.plugins.builtin  # noqa: F401
    except Exception:
        pass
    emit_plugin_event("plugins_loaded", count=len(manifests), tool_plugins=len(tool_plugins))
    return {
        "manifests": manifests,
        "tool_plugin_count": len(tool_plugins),
        "runtime": runtime.status(),
    }


def register_provider_plugin(manifest: dict[str, Any]) -> dict[str, Any]:
    m = register_manifest(manifest)
    emit_plugin_event("plugin_registered", plugin_id=m.plugin_id)
    return m.to_dict()
