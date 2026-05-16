# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin runtime host with lifecycle states (Phase 2 Step 9)."""

from __future__ import annotations

from typing import Any

from app.plugins.plugin_events import emit_plugin_event
from app.plugins.plugin_manifest import PluginManifest
from app.plugins.plugin_registry import get_plugin_manifest, list_plugin_manifests

_PLUGIN_STATES: dict[str, dict[str, Any]] = {}


def _set_state(plugin_id: str, state: str, **extra: Any) -> dict[str, Any]:
    row = {
        "plugin_id": plugin_id,
        "state": state,
        **extra,
    }
    _PLUGIN_STATES[plugin_id] = row
    return row


def list_plugin_runtime_states() -> dict[str, dict[str, Any]]:
    manifests = list_plugin_manifests()
    out: dict[str, dict[str, Any]] = {}
    for m in manifests:
        pid = str(m.get("plugin_id") or "")
        out[pid] = _PLUGIN_STATES.get(pid) or {"plugin_id": pid, "state": "registered"}
    return out


def load_plugin(plugin_id: str) -> dict[str, Any]:
    m = get_plugin_manifest(plugin_id)
    if not m:
        _set_state(plugin_id, "failed", error="unknown_plugin")
        emit_plugin_event("plugin_failed", plugin_id=plugin_id)
        try:
            from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

            emit_mc_runtime_event("plugin_failed", plugin_id=plugin_id)
        except Exception:
            pass
        return _PLUGIN_STATES[plugin_id]
    try:
        manifest = PluginManifest.from_dict(m)
        if not manifest.plugin_id:
            raise ValueError("invalid_manifest")
        row = _set_state(plugin_id, "loaded", version=manifest.version)
        row = _set_state(plugin_id, "active", capabilities=manifest.capabilities)
        emit_plugin_event("plugin_loaded", plugin_id=plugin_id)
        try:
            from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

            emit_mc_runtime_event("plugin_loaded", plugin_id=plugin_id, category="plugin")
        except Exception:
            pass
        return row
    except Exception as exc:
        _set_state(plugin_id, "failed", error=str(exc)[:200])
        emit_plugin_event("plugin_failed", plugin_id=plugin_id, error=str(exc)[:200])
        return _PLUGIN_STATES[plugin_id]


def disable_plugin(plugin_id: str) -> dict[str, Any]:
    return _set_state(plugin_id, "disabled")


class PluginRuntime:
    def __init__(self) -> None:
        self._started = False

    def start(self) -> None:
        self._started = True

    def status(self) -> dict[str, Any]:
        return {
            "started": self._started,
            "manifest_count": len(list_plugin_manifests()),
            "states": list_plugin_runtime_states(),
            "sandbox": "capability_declarations_only",
        }
