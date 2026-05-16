# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Automation pack metadata and runtime control (Phase 3 Step 1–2)."""

from __future__ import annotations

from typing import Any

from app.plugins.plugin_registry import list_plugin_manifests
from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

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


def _pack_states(st: dict[str, Any]) -> dict[str, Any]:
    ps = st.setdefault("automation_pack_states", {})
    return ps if isinstance(ps, dict) else {}


def list_automation_packs() -> list[dict[str, Any]]:
    return [p for p in list_automation_packs_with_health() if p.get("pack_type")]


def list_automation_packs_with_health() -> list[dict[str, Any]]:
    st = load_runtime_state()
    states = _pack_states(st)
    from app.plugins.plugin_runtime import list_plugin_runtime_states

    runtime_states = list_plugin_runtime_states()
    packs: list[dict[str, Any]] = []
    for m in list_plugin_manifests():
        pack = m.get("automation_pack")
        if not pack and "automation_pack" not in (m.get("capabilities") or []):
            continue
        pid = str(m.get("plugin_id") or "")
        ps = states.get(pid) if isinstance(states.get(pid), dict) else {}
        rt = runtime_states.get(pid) or {}
        enabled = ps.get("enabled", True) if ps else True
        base_row = {
            "plugin_id": pid,
            "pack_type": pack or "custom",
            "name": m.get("name"),
            "permissions": list(m.get("permissions") or []),
            "verified": m.get("verified"),
            "enabled": enabled,
            "health": rt.get("state", "registered"),
            "warning": rt.get("state") == "warning",
            "failed": rt.get("state") == "failed",
        }
        try:
            from app.runtime.automation_pack_runtime import enrich_pack_runtime_row

            packs.append(enrich_pack_runtime_row(base_row))
        except Exception:
            packs.append(base_row)
    return packs


def set_automation_pack_enabled(plugin_id: str, *, enabled: bool) -> dict[str, Any]:
    st = load_runtime_state()
    states = _pack_states(st)
    pid = plugin_id.strip()
    states[pid] = {"enabled": enabled, "updated_at": utc_now_iso()}
    audit = st.setdefault("plugin_governance_audit", [])
    if isinstance(audit, list):
        audit.append(
            {
                "action": "automation_pack_enable" if enabled else "automation_pack_disable",
                "plugin_id": pid,
                "timestamp": utc_now_iso(),
            }
        )
    save_runtime_state(st)
    try:
        from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

        emit_mc_runtime_event(
            "plugin_pack_toggled",
            plugin_id=pid,
            enabled=enabled,
            category="plugin",
        )
    except Exception:
        pass
    return {"plugin_id": pid, "enabled": enabled}


def get_automation_pack(plugin_id: str) -> dict[str, Any] | None:
    for p in list_automation_packs_with_health():
        if p.get("plugin_id") == plugin_id:
            return p
    return None
