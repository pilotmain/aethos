# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded operational intelligence for Mission Control (Phase 3 Step 1–2)."""

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
    privacy_risk = sum(1 for e in events if e.get("category") == "privacy")
    if privacy_risk:
        insights.append({"kind": "privacy_risk_events", "severity": "warning", "message": f"{privacy_risk} privacy events in tail"})
    verify_fail = sum(1 for e in events if "verif" in str(e.get("event_type") or "") and "fail" in str(e.get("event_type") or ""))
    if verify_fail:
        insights.append({"kind": "verification_failures", "severity": "error", "message": "Verification failures detected"})

    repair_success_rate = _repair_success_rate(st)
    if repair_success_rate is not None and repair_success_rate < 0.5:
        insights.append(
            {
                "kind": "repair_success_low",
                "severity": "warning",
                "message": f"Repair success rate {repair_success_rate:.0%}",
            }
        )

    worker_signals = _worker_reliability_signals(st)
    if worker_signals.get("low_reliability_workers"):
        insights.append(
            {
                "kind": "worker_reliability",
                "severity": "warning",
                "message": worker_signals.get("summary") or "Worker reliability mixed",
            }
        )

    return {
        "insights": insights[:12],
        "event_warnings": len(events),
        "installed_plugin_count": len(plugins) if isinstance(plugins, list) else 0,
        "repair_tracked": len(repairs) if isinstance(repairs, dict) else 0,
        "repair_success_rate": repair_success_rate,
        "workspace_confidence_drift": _workspace_confidence_drift(st),
        "repeated_failure_patterns": _repeated_failures(events),
        "worker_reliability": worker_signals,
    }


def _worker_reliability_signals(st: dict[str, Any]) -> dict[str, Any]:
    wm = st.get("worker_memory") or {}
    low: list[str] = []
    if isinstance(wm, dict):
        for wid, mem in wm.items():
            if isinstance(mem, dict) and len(mem.get("recent_failures") or []) >= 2:
                low.append(str(wid))
    return {
        "low_reliability_workers": low[:8],
        "worker_count": len(wm) if isinstance(wm, dict) else 0,
        "summary": f"{len(low)} worker(s) with repeated failures" if low else "Workers stable",
    }


def _repair_success_rate(st: dict[str, Any]) -> float | None:
    repairs = st.get("repair_contexts") or {}
    if not isinstance(repairs, dict):
        return None
    ok = fail = 0
    for pid, bucket in repairs.items():
        if pid == "latest_by_project" or not isinstance(bucket, dict):
            continue
        for row in bucket.values():
            if not isinstance(row, dict):
                continue
            vr = row.get("verification_result") or {}
            if isinstance(vr, dict) and vr.get("verified") is True:
                ok += 1
            elif row.get("status") == "failed":
                fail += 1
    total = ok + fail
    return round(ok / total, 4) if total else None


def _workspace_confidence_drift(st: dict[str, Any]) -> dict[str, Any] | None:
    reg = st.get("project_registry") or {}
    projects = reg.get("projects") if isinstance(reg, dict) else {}
    if not isinstance(projects, dict) or not projects:
        return None
    scores = [float(p.get("confidence") or 0) for p in projects.values() if isinstance(p, dict) and p.get("confidence")]
    if not scores:
        return None
    avg = sum(scores) / len(scores)
    return {"average_confidence": round(avg, 3), "project_count": len(scores)}


def _repeated_failures(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for e in events:
        et = str(e.get("event_type") or "")
        if "fail" in et or e.get("severity") in ("error", "critical"):
            counts[et] = counts.get(et, 0) + int(e.get("count") or 1)
    return [{"event_type": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])[:6]]
