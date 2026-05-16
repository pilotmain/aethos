# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime plugin marketplace catalog and install flows (Phase 3 Step 1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.plugins.plugin_installer import (
    install_plugin,
    list_installed_plugin_ids,
    load_installed_manifest,
    uninstall_plugin,
    upgrade_plugin,
)
from app.plugins.plugin_registry import get_plugin_manifest, list_plugin_manifests
from app.plugins.plugin_runtime import build_plugin_health_panel, list_plugin_runtime_states

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "aethos_marketplace" / "runtime_plugins.json"


def _load_catalog() -> list[dict[str, Any]]:
    if not _CATALOG_PATH.is_file():
        return []
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    rows = data.get("plugins")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _enrich_entry(entry: dict[str, Any]) -> dict[str, Any]:
    pid = str(entry.get("plugin_id") or "")
    installed_ids = set(list_installed_plugin_ids())
    states = list_plugin_runtime_states()
    st = states.get(pid) or {}
    row = dict(entry)
    row["installed"] = pid in installed_ids or bool(entry.get("installed"))
    row["official"] = bool(entry.get("official") or entry.get("trust_tier") == "official")
    row["runtime_state"] = st.get("state", "registered")
    row["downloads"] = int(entry.get("downloads") or 0)
    return row


def list_marketplace_plugins() -> list[dict[str, Any]]:
    catalog = {_enrich_entry(e)["plugin_id"]: _enrich_entry(e) for e in _load_catalog()}
    for m in list_plugin_manifests():
        pid = str(m.get("plugin_id") or "")
        if pid and pid not in catalog:
            catalog[pid] = _enrich_entry(m)
    return list(catalog.values())


def get_marketplace_plugin(plugin_id: str) -> dict[str, Any] | None:
    pid = (plugin_id or "").strip()
    for row in list_marketplace_plugins():
        if str(row.get("plugin_id") or "") == pid:
            return row
    return None


def marketplace_install(plugin_id: str, *, version: str | None = None) -> dict[str, Any]:
    entry = get_marketplace_plugin(plugin_id)
    if not entry:
        raise ValueError("unknown_plugin")
    manifest = dict(entry)
    manifest.pop("runtime_state", None)
    manifest.pop("downloads", None)
    return install_plugin(manifest, version=version or str(entry.get("version") or "1.0.0"))


def marketplace_uninstall(plugin_id: str) -> dict[str, Any]:
    if plugin_id.strip() in ("aethos-builtin-tools", "vercel-provider") and get_plugin_manifest(plugin_id):
        # Allow uninstall of non-system; orchestrator builtins stay in registry
        pass
    return uninstall_plugin(plugin_id)


def marketplace_upgrade(plugin_id: str, *, version: str | None = None) -> dict[str, Any]:
    entry = get_marketplace_plugin(plugin_id)
    if not entry:
        raise ValueError("unknown_plugin")
    manifest = dict(entry)
    if version:
        manifest["version"] = version
    return upgrade_plugin(plugin_id, manifest)


def marketplace_summary() -> dict[str, Any]:
    health = build_plugin_health_panel()
    plugins = list_marketplace_plugins()
    return {
        "available_count": len(plugins),
        "installed_count": len([p for p in plugins if p.get("installed")]),
        "plugin_health": health,
        "installed_plugins": [p for p in plugins if p.get("installed")],
        "available_plugins": [p for p in plugins if not p.get("installed")],
    }
