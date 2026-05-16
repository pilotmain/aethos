# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational intelligence engine — signals, insights, enterprise state (Phase 3 Step 10)."""

from __future__ import annotations

from typing import Any

from app.runtime.automation_pack_runtime import build_automation_pack_runtime_truth
from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display
from app.services.operational_intelligence import build_operational_intelligence
from app.services.workspace_runtime_intelligence import build_operational_risk, build_workspace_intelligence


def build_operational_intelligence_engine(ort: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full engine output: base intel + signals + suggestions + enterprise state."""
    base = build_operational_intelligence(ort)
    signals = build_intelligence_signals(ort, base)
    suggestions = build_proactive_suggestions(signals, base)
    packs = build_automation_pack_runtime_truth()
    workspace = build_workspace_intelligence()
    risk = build_operational_risk()
    return {
        **base,
        "signals": signals,
        "suggestions": suggestions[:10],
        "automation_pack_runtime": packs,
        "workspace_snapshot": {
            "project_count": workspace.get("project_count"),
            "risk_signals": workspace.get("risk_signals"),
        },
        "operational_risk": risk,
        "runtime_insights": build_runtime_insights(signals, base, packs),
        "enterprise_operational_state": build_enterprise_operational_state(signals, base, packs, risk),
        "summaries": build_operational_summaries(base, packs, workspace, risk),
    }


def build_intelligence_signals(
    ort: dict[str, Any] | None,
    base: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ort = ort or {}
    base = base or build_operational_intelligence(ort)
    rel = ort.get("reliability") or {}
    events = aggregate_events_for_display(limit=32, min_severity="warning")
    st = load_runtime_state()
    signals: list[dict[str, Any]] = []

    dep_fails = sum(1 for e in events if "deploy" in str(e.get("event_type") or "") and "fail" in str(e.get("event_type") or ""))
    if dep_fails:
        signals.append({"kind": "deployment_reliability_trend", "severity": "warning", "value": dep_fails})

    if int(rel.get("provider_failures") or 0) > 0:
        signals.append({"kind": "provider_instability_trend", "severity": "error", "value": rel.get("provider_failures")})

    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    if isinstance(repairs, dict) and len(repairs) > 3:
        signals.append({"kind": "repair_churn", "severity": "warning", "value": len(repairs)})

    if int(rel.get("retry_pressure_events") or 0) > 0:
        signals.append({"kind": "retry_pressure_pattern", "severity": "warning", "value": rel.get("retry_pressure_events")})

    wr = base.get("worker_reliability") or {}
    if wr.get("low_reliability_workers"):
        signals.append({"kind": "worker_reliability", "severity": "warning", "value": len(wr["low_reliability_workers"])})

    drift = base.get("workspace_confidence_drift")
    if drift and float(drift.get("average_confidence") or 1) < 0.5:
        signals.append({"kind": "workspace_degradation", "severity": "warning", "value": drift})

    packs = build_automation_pack_runtime_truth()
    failed_packs = [p for p in packs.get("packs") or [] if p.get("failed")]
    if failed_packs:
        signals.append({"kind": "automation_effectiveness", "severity": "info", "value": len(failed_packs)})

    recovery = (st.get("runtime_metrics") or {}).get("runtime_continuity") or {}
    if int(recovery.get("restart_recovery_attempts") or 0) > int(recovery.get("restart_recovery_successes") or 0):
        signals.append({"kind": "runtime_recovery_quality", "severity": "warning", "value": "degraded"})

    for ins in base.get("insights") or []:
        if isinstance(ins, dict) and ins.get("kind") == "plugin_instability":
            signals.append({"kind": "plugin_instability", "severity": ins.get("severity", "warning")})

    return signals[:16]


def build_proactive_suggestions(
    signals: list[dict[str, Any]],
    base: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Advisory only — non-autonomous."""
    suggestions: list[dict[str, Any]] = []
    kinds = {s.get("kind") for s in signals}
    if "deployment_reliability_trend" in kinds:
        suggestions.append(
            {
                "kind": "deployment_instability",
                "message": "Deployment instability detected — consider rollback or verification rerun.",
                "advisory": True,
            }
        )
    if "provider_instability_trend" in kinds:
        suggestions.append(
            {
                "kind": "provider_unreliable",
                "message": "Provider becoming unreliable — recommend provider fallback review.",
                "advisory": True,
            }
        )
    if "repair_churn" in kinds:
        suggestions.append(
            {
                "kind": "repair_loop",
                "message": "Repair loop repeating — recommend repair escalation or workspace audit.",
                "advisory": True,
            }
        )
    if "workspace_degradation" in kinds:
        suggestions.append(
            {
                "kind": "workspace_confidence",
                "message": "Workspace confidence degrading — recommend workspace verification.",
                "advisory": True,
            }
        )
    if "plugin_instability" in kinds:
        suggestions.append(
            {
                "kind": "plugin_failures",
                "message": "Plugin causing repeated failures — consider disabling affected automation pack.",
                "advisory": True,
            }
        )
    if base and base.get("repair_success_rate") is not None and base["repair_success_rate"] < 0.5:
        suggestions.append(
            {
                "kind": "verification_rerun",
                "message": "Repair success low — recommend rerunning verification.",
                "advisory": True,
            }
        )
    return suggestions


def build_runtime_insights(
    signals: list[dict[str, Any]],
    base: dict[str, Any],
    packs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "signal_count": len(signals),
        "insight_count": len(base.get("insights") or []),
        "automation_runs": len(packs.get("recent_executions") or []),
        "high_severity_signals": [s for s in signals if s.get("severity") in ("error", "critical")][:6],
    }


def build_enterprise_operational_state(
    signals: list[dict[str, Any]],
    base: dict[str, Any],
    packs: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    return {
        "health": "degraded" if any(s.get("severity") == "error" for s in signals) else "stable",
        "active_risk_count": len(risk.get("risk_signals") or []),
        "automation_pack_count": packs.get("pack_count", 0),
        "repair_success_rate": base.get("repair_success_rate"),
        "event_warnings": base.get("event_warnings", 0),
    }


def build_operational_summaries(
    base: dict[str, Any],
    packs: dict[str, Any],
    workspace: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, str]:
    ws_summ = workspace.get("summaries") or {}
    return {
        "runtime_operational_summary": f"{base.get('event_warnings', 0)} warning event(s); "
        f"repair rate {base.get('repair_success_rate') or 'n/a'}.",
        "provider_health_summary": f"Provider failures tracked in operational intelligence.",
        "automation_effectiveness_summary": f"{packs.get('pack_count', 0)} pack(s); "
        f"{len(packs.get('recent_executions') or [])} recent execution(s).",
        "workspace_operational_summary": ws_summ.get("workspace_operational_summary", "Workspace tracked."),
        "governance_summary": "Governance timeline includes automation, deliverables, and provider events.",
        "deployment_reliability_summary": f"Deployment churn signal: {risk.get('deployment_churn', 0)}.",
        "repair_effectiveness_summary": f"Repair churn: {risk.get('repair_churn', 0)} active context(s).",
    }
