# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded operational intelligence for Mission Control (Phase 3 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display


def build_operational_intelligence(ort: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    ort = ort or {}
    rel = ort.get("reliability") or {}
    events = aggregate_events_for_display(limit=32, min_severity="warning")
    plugins = st.get("installed_plugins") or []
    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    insights: list[dict[str, Any]] = []

    if int(ort.get("queued_tasks") or 0) > 8:
        insights.append({"kind": "deployment_bottleneck", "severity": "warning", "message": "Queue depth elevated"})
    if int(rel.get("retry_pressure_events") or 0) > 0:
        insights.append({"kind": "retry_pressure", "severity": "warning", "message": "Retry pressure detected"})
    if int(rel.get("provider_failures") or 0) > 0:
        insights.append({"kind": "provider_instability", "severity": "error", "message": "Provider failures recorded"})
    if isinstance(repairs, dict) and len(repairs) > 5:
        insights.append({"kind": "repair_volume", "severity": "info", "message": "Multiple active repair contexts"})
    failed_plugins = sum(
        1
        for e in events
        if e.get("category") == "plugin" and str(e.get("severity") or "") in ("error", "critical")
    )
    if failed_plugins:
        insights.append({"kind": "plugin_instability", "severity": "warning", "message": "Plugin runtime warnings present"})

    return {
        "insights": insights[:12],
        "event_warnings": len(events),
        "installed_plugin_count": len(plugins) if isinstance(plugins, list) else 0,
        "repair_tracked": len(repairs) if isinstance(repairs, dict) else 0,
    }
