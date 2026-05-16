# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime governance and audit visibility (Phase 3 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_event_intelligence import list_normalized_events


def build_governance_audit(*, limit: int = 40) -> dict[str, Any]:
    st = load_runtime_state()
    plugin_audit = st.get("plugin_governance_audit") or []
    if not isinstance(plugin_audit, list):
        plugin_audit = []
    provider_ops = st.get("operator_provider_actions") or []
    if not isinstance(provider_ops, list):
        provider_ops = []
    events = list_normalized_events(limit=limit)
    privacy_events = [e for e in events if e.get("category") == "privacy"]
    repair_events = [e for e in events if e.get("category") == "repair"]
    deploy_events = [e for e in events if e.get("category") == "deployment"]
    brain_decisions = st.get("brain_decisions") or []
    if not isinstance(brain_decisions, list):
        brain_decisions = []
    return {
        "plugin_installs": [_humanize_audit(r) for r in plugin_audit[-20:]],
        "provider_operations": [_humanize_audit(r) for r in provider_ops[-20:]],
        "privacy_enforcement": privacy_events[-12:],
        "repair_operations": repair_events[-12:],
        "deployment_operations": deploy_events[-12:],
        "brain_routing_decisions": brain_decisions[-16:],
        "permissions_tracked": _collect_permissions(st),
        "summary": {
            "plugin_actions": len(plugin_audit),
            "provider_actions": len(provider_ops),
            "privacy_events": len(privacy_events),
        },
    }


def _humanize_audit(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    action = str(row.get("action") or row.get("operation") or "action")
    pid = row.get("plugin_id") or row.get("provider")
    return {**row, "summary": f"{action}: {pid}" if pid else action}


def _collect_permissions(st: dict[str, Any]) -> list[str]:
    perms: set[str] = set()
    from app.plugins.plugin_registry import list_plugin_manifests

    for m in list_plugin_manifests():
        for p in m.get("permissions") or []:
            perms.add(str(p))
    return sorted(perms)[:48]
