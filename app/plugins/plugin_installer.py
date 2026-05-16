# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin install / uninstall / upgrade lifecycle (Phase 3 Step 1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.paths import get_plugins_dir
from app.plugins.plugin_events import emit_plugin_event
from app.plugins.plugin_manifest import PluginManifest
from app.plugins.plugin_registry import get_plugin_manifest, register_manifest
from app.plugins.plugin_runtime import disable_plugin, safe_load_plugin
from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_LIFECYCLE = frozenset(
    {"registered", "installed", "loaded", "active", "warning", "failed", "disabled", "deprecated"}
)


def _plugin_dir(plugin_id: str) -> Path:
    return get_plugins_dir() / plugin_id.strip()


def _manifest_path(plugin_id: str) -> Path:
    return _plugin_dir(plugin_id) / "manifest.json"


def list_installed_plugin_ids() -> list[str]:
    st = load_runtime_state()
    rows = st.get("installed_plugins")
    if not isinstance(rows, list):
        return []
    return [str(x) for x in rows if x]


def _set_installed(plugin_id: str, *, add: bool) -> None:
    st = load_runtime_state()
    rows = st.setdefault("installed_plugins", [])
    if not isinstance(rows, list):
        rows = []
        st["installed_plugins"] = rows
    pid = plugin_id.strip()
    if add and pid not in rows:
        rows.append(pid)
    elif not add and pid in rows:
        rows.remove(pid)
    audit = st.setdefault("plugin_governance_audit", [])
    if isinstance(audit, list):
        audit.append(
            {
                "action": "install" if add else "uninstall",
                "plugin_id": pid,
                "timestamp": utc_now_iso(),
            }
        )
        if len(audit) > 200:
            del audit[: len(audit) - 200]
    save_runtime_state(st)


def validate_manifest_for_install(manifest: dict[str, Any]) -> None:
    m = PluginManifest.from_dict(manifest)
    if not m.plugin_id or m.plugin_id == "unknown":
        raise ValueError("invalid_plugin_id")
    if not m.permissions and m.trust_tier in ("community", "experimental"):
        raise ValueError("permissions_required_for_untrusted_tier")


def install_plugin(manifest: dict[str, Any], *, version: str | None = None) -> dict[str, Any]:
    """Install plugin to ~/.aethos/plugins/{id}/manifest.json and load safely."""
    validate_manifest_for_install(manifest)
    m = PluginManifest.from_dict(manifest)
    if version:
        m.version = version
    pid = m.plugin_id
    pdir = _plugin_dir(pid)
    pdir.mkdir(parents=True, exist_ok=True)
    payload = m.to_dict()
    payload["installed"] = True
    payload["installed_at"] = datetime.now(timezone.utc).isoformat()
    _manifest_path(pid).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    register_manifest(m)
    _set_installed(pid, add=True)
    emit_plugin_event("plugin_installed", plugin_id=pid, version=m.version)
    row = safe_load_plugin(pid)
    state = str(row.get("state") or "installed")
    if state not in _LIFECYCLE:
        state = "installed"
    return {"plugin_id": pid, "state": state, "version": m.version, "installed": True}


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    pid = (plugin_id or "").strip()
    if not pid:
        raise ValueError("plugin_id_required")
    disable_plugin(pid)
    pdir = _plugin_dir(pid)
    if pdir.is_dir():
        for f in pdir.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)
        try:
            pdir.rmdir()
        except OSError:
            pass
    _set_installed(pid, add=False)
    emit_plugin_event("plugin_uninstalled", plugin_id=pid)
    return {"plugin_id": pid, "state": "registered", "installed": False}


def upgrade_plugin(plugin_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    pid = (plugin_id or "").strip()
    uninstall_plugin(pid)
    manifest = dict(manifest)
    manifest["plugin_id"] = pid
    return install_plugin(manifest, version=str(manifest.get("version") or "1.0.0"))


def load_installed_manifest(plugin_id: str) -> dict[str, Any] | None:
    path = _manifest_path(plugin_id)
    if not path.is_file():
        return get_plugin_manifest(plugin_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def sync_installed_from_disk() -> int:
    """Register manifests found on disk into runtime registry."""
    root = get_plugins_dir()
    root.mkdir(parents=True, exist_ok=True)
    n = 0
    for pdir in root.iterdir():
        if not pdir.is_dir():
            continue
        mf = pdir / "manifest.json"
        if not mf.is_file():
            continue
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
            register_manifest(data)
            _set_installed(str(data.get("plugin_id") or pdir.name), add=True)
            n += 1
        except (json.JSONDecodeError, ValueError):
            continue
    return n
