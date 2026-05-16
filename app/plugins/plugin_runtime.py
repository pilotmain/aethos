# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin runtime host with lifecycle states (Phase 2 Step 9–10)."""

from __future__ import annotations

from typing import Any

from app.plugins.plugin_events import emit_plugin_event
from app.plugins.plugin_manifest import PluginManifest
from app.plugins.plugin_registry import get_plugin_manifest, list_plugin_manifests

_PLUGIN_STATES: dict[str, dict[str, Any]] = {}


def _set_state(plugin_id: str, state: str, **extra: Any) -> dict[str, Any]:
    row = {"plugin_id": plugin_id, "state": state, **extra}
    _PLUGIN_STATES[plugin_id] = row
    return row


def list_plugin_runtime_states() -> dict[str, dict[str, Any]]:
    manifests = list_plugin_manifests()
    out: dict[str, dict[str, Any]] = {}
    for m in manifests:
        pid = str(m.get("plugin_id") or "")
        out[pid] = _PLUGIN_STATES.get(pid) or {"plugin_id": pid, "state": "registered"}
    return out


def _emit_plugin_mc(event: str, plugin_id: str, **kw: Any) -> None:
    try:
        from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

        emit_mc_runtime_event(event, plugin_id=plugin_id, category="plugin", **kw)
    except Exception:
        pass


def load_plugin(plugin_id: str) -> dict[str, Any]:
    """Load plugin — failures are isolated; orchestrator runtime continues."""
    return safe_load_plugin(plugin_id)


def safe_load_plugin(plugin_id: str) -> dict[str, Any]:
    m = get_plugin_manifest(plugin_id)
    if not m:
        row = _set_state(plugin_id, "failed", error="unknown_plugin")
        emit_plugin_event("plugin_failed", plugin_id=plugin_id)
        _emit_plugin_mc("plugin_failed", plugin_id)
        return row
    try:
        manifest = PluginManifest.from_dict(m)
        if not manifest.plugin_id:
            raise ValueError("invalid_manifest")
        if manifest.trust_tier == "experimental":
            _set_state(plugin_id, "warning", note="experimental_tier")
        _set_state(plugin_id, "loaded", version=manifest.version, trust_tier=manifest.trust_tier)
        row = _set_state(plugin_id, "active", capabilities=manifest.capabilities)
        emit_plugin_event("plugin_loaded", plugin_id=plugin_id)
        _emit_plugin_mc("plugin_loaded", plugin_id)
        return row
    except Exception as exc:
        row = _set_state(plugin_id, "failed", error=str(exc)[:200])
        emit_plugin_event("plugin_failed", plugin_id=plugin_id, error=str(exc)[:200])
        _emit_plugin_mc("plugin_failed", plugin_id, severity="error")
        return row


def disable_plugin(plugin_id: str) -> dict[str, Any]:
    return _set_state(plugin_id, "disabled")


def reload_plugin(plugin_id: str) -> dict[str, Any]:
    disable_plugin(plugin_id)
    return safe_load_plugin(plugin_id)


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
