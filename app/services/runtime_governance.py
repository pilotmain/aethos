# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime governance and audit visibility (Phase 3 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_event_intelligence import list_normalized_events


def build_governance_timeline(*, limit: int = 32) -> dict[str, Any]:
    """Operational timeline — human-readable, newest first."""
    import time

    t0 = time.monotonic()
    audit = build_governance_audit(limit=limit)
    entries: list[dict[str, Any]] = []
    for row in audit.get("plugin_installs") or []:
        if isinstance(row, dict):
            entries.append(
                {
                    "at": row.get("timestamp"),
                    "kind": "plugin",
                    "who": "operator",
                    "what": row.get("summary") or row.get("action"),
                    "privacy_mode": None,
                }
            )
    for row in audit.get("provider_operations") or []:
        if isinstance(row, dict):
            entries.append(
                {
                    "at": row.get("timestamp") or row.get("at"),
                    "kind": "provider",
                    "who": row.get("actor") or "runtime",
                    "what": _humanize_provider_op(row),
                    "provider": row.get("provider"),
                }
            )
    for row in audit.get("brain_routing_decisions") or []:
        if isinstance(row, dict):
            entries.append(
                {
                    "at": row.get("created_at"),
                    "kind": "brain",
                    "who": "brain router",
                    "what": f"Routed {row.get('task')} to {row.get('selected_provider')}/{row.get('selected_model')}",
                    "privacy_mode": row.get("privacy_mode"),
                }
            )
    for row in audit.get("deployment_operations") or []:
        if isinstance(row, dict):
            entries.append(
                {
                    "at": row.get("timestamp"),
                    "kind": "deployment",
                    "who": "deployment",
                    "what": _humanize_deployment(row),
                }
            )
    for row in audit.get("repair_operations") or []:
        if isinstance(row, dict):
            entries.append(
                {
                    "at": row.get("timestamp"),
                    "kind": "repair",
                    "who": "repair flow",
                    "what": _humanize_repair(row),
                }
            )
    for row in audit.get("automation_pack_operations") or []:
        if isinstance(row, dict):
            entries.append(
                {
                    "at": row.get("timestamp"),
                    "kind": "automation_pack",
                    "who": "automation",
                    "what": row.get("summary") or str(row.get("pack_id") or "pack"),
                }
            )
    for row in audit.get("privacy_enforcement") or []:
        if isinstance(row, dict):
            entries.append(
                {
                    "at": row.get("timestamp"),
                    "kind": "privacy",
                    "who": "privacy gate",
                    "what": str(row.get("event_type") or "privacy"),
                    "privacy_mode": (row.get("payload") or {}).get("privacy_mode") if isinstance(row.get("payload"), dict) else None,
                }
            )
    entries.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    timeline = entries[:limit]
    try:
        from app.services.mission_control.runtime_metrics_discipline import record_timeline_build

        record_timeline_build(entry_count=len(timeline), duration_ms=(time.monotonic() - t0) * 1000.0)
    except Exception:
        pass
    return {"timeline": timeline, "summary": audit.get("summary")}


def _humanize_provider_op(row: dict[str, Any]) -> str:
    prov = row.get("provider") or row.get("provider_id") or "provider"
    act = row.get("action") or row.get("operation") or "action"
    return f"{prov} — {act}"


def _humanize_deployment(row: dict[str, Any]) -> str:
    et = str(row.get("event_type") or "deployment")
    pl = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    pid = pl.get("project_id") or row.get("project_id") or ""
    return f"{et}" + (f" for {pid}" if pid else "")


def _humanize_repair(row: dict[str, Any]) -> str:
    et = str(row.get("event_type") or "repair")
    pl = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    pid = pl.get("project_id") or ""
    return f"{et}" + (f" on {pid}" if pid else "")


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
    pack_states = st.get("automation_pack_states") or {}
    pack_ops: list[dict[str, Any]] = []
    if isinstance(pack_states, dict):
        for pack_id, row in list(pack_states.items())[-12:]:
            if isinstance(row, dict) and row.get("last_event"):
                pack_ops.append(
                    {
                        "pack_id": pack_id,
                        "summary": row.get("last_event"),
                        "timestamp": row.get("updated_at"),
                    }
                )
    return {
        "plugin_installs": [_humanize_audit(r) for r in plugin_audit[-20:]],
        "provider_operations": [_humanize_audit(r) for r in provider_ops[-20:]],
        "privacy_enforcement": privacy_events[-12:],
        "repair_operations": repair_events[-12:],
        "deployment_operations": deploy_events[-12:],
        "brain_routing_decisions": brain_decisions[-16:],
        "automation_pack_operations": pack_ops,
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
