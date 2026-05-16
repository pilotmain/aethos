# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace / project runtime intelligence (Phase 3 Step 1, expanded Step 9)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.runtime.workspace_operational_memory import list_research_chains
from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display
from app.services.operator_context import build_operator_context_panel


def build_workspace_intelligence() -> dict[str, Any]:
    st = load_runtime_state()
    op = build_operator_context_panel()
    registry = op.get("project_registry") or st.get("project_registry") or {}
    projects = registry.get("projects") if isinstance(registry, dict) else {}
    identities = op.get("deployment_identities") or {}
    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(projects, dict):
        for pid, row in list(projects.items())[:24]:
            if not isinstance(row, dict):
                continue
            ident = identities.get(pid) if isinstance(identities, dict) else None
            repair_id = repairs.get(pid) if isinstance(repairs, dict) else None
            conf = row.get("confidence") or row.get("repo_confidence")
            rows.append(
                {
                    "project_id": pid,
                    "confidence": conf,
                    "deployment_linked": bool(ident),
                    "repair_active": bool(repair_id),
                    "provider": (ident or {}).get("provider") if isinstance(ident, dict) else None,
                    "verification_state": row.get("verification_state"),
                    "risk_level": _project_risk(row, bool(repair_id), conf),
                }
            )
    risk_signals = _build_risk_signals(st, rows)
    deployment_signals = _deployment_signals(st, op)
    repair_signals = _repair_signals(st, repairs)
    chains = list_research_chains(limit=8)
    return {
        "projects": rows,
        "project_count": len(rows),
        "deployment_linked_count": sum(1 for r in rows if r.get("deployment_linked")),
        "repair_active_count": sum(1 for r in rows if r.get("repair_active")),
        "risk_signals": risk_signals,
        "repair_signals": repair_signals,
        "deployment_signals": deployment_signals,
        "workspace_confidence": _workspace_confidence_summary(rows),
        "research_continuity": {
            "active_chains": len(chains),
            "chains": chains[:6],
        },
        "summaries": build_workspace_operational_summaries(st, op, rows),
    }


def build_operational_risk() -> dict[str, Any]:
    """Bounded operational risk surface for runtime truth."""
    st = load_runtime_state()
    wi = build_workspace_intelligence()
    events = aggregate_events_for_display(limit=24, min_severity="warning")
    high_risk = [r for r in wi.get("projects") or [] if r.get("risk_level") == "high"]
    return {
        "high_risk_projects": high_risk[:8],
        "risk_signals": wi.get("risk_signals") or [],
        "retry_pressure": sum(1 for e in events if "retry" in str(e.get("event_type") or "")),
        "deployment_churn": wi.get("deployment_signals", {}).get("recent_count", 0),
        "repair_churn": wi.get("repair_signals", {}).get("active_count", 0),
        "workspace_confidence": wi.get("workspace_confidence"),
    }


def build_workspace_operational_summaries(
    st: dict[str, Any] | None = None,
    op: dict[str, Any] | None = None,
    project_rows: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    st = st or load_runtime_state()
    op = op or build_operator_context_panel()
    project_rows = project_rows or []
    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    providers = op.get("provider_ids") or []
    chains = list_research_chains(limit=4)
    return {
        "project_summary": f"{len(project_rows)} tracked project(s), "
        f"{sum(1 for r in project_rows if r.get('deployment_linked'))} deployment-linked.",
        "deployment_history_summary": f"{len(op.get('recent_provider_actions') or [])} recent provider action(s).",
        "repair_trend_summary": f"{len(repairs) if isinstance(repairs, dict) else 0} project(s) with active repair context.",
        "provider_usage_summary": f"Providers in use: {', '.join(str(p) for p in providers[:6]) or 'none'}.",
        "research_summary": f"{len(chains)} research chain(s) with linked deliverables.",
        "workspace_operational_summary": _workspace_confidence_summary(project_rows),
    }


def _project_risk(row: dict[str, Any], repair_active: bool, confidence: Any) -> str:
    if repair_active and str(confidence or "").lower() in ("low", "medium"):
        return "high"
    if repair_active:
        return "medium"
    if str(confidence or "").lower() == "low":
        return "medium"
    return "low"


def _build_risk_signals(st: dict[str, Any], projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    high = [p for p in projects if p.get("risk_level") == "high"]
    if high:
        signals.append({"kind": "high_risk_projects", "count": len(high), "severity": "warning"})
    events = aggregate_events_for_display(limit=16, min_severity="error")
    dep_fail = sum(1 for e in events if "deploy" in str(e.get("event_type") or "") and "fail" in str(e.get("event_type") or ""))
    if dep_fail >= 2:
        signals.append({"kind": "repeated_deployment_failures", "count": dep_fail, "severity": "error"})
    wm = st.get("worker_memory") or {}
    churn = sum(
        1
        for mem in (wm.values() if isinstance(wm, dict) else [])
        if isinstance(mem, dict) and len(mem.get("recent_failures") or []) >= 2
    )
    if churn:
        signals.append({"kind": "repair_churn", "count": churn, "severity": "warning"})
    ort = st.get("orchestration") or {}
    if int((ort.get("queued_tasks") if isinstance(ort, dict) else 0) or 0) > 6:
        signals.append({"kind": "retry_pressure", "severity": "warning"})
    return signals[:12]


def _deployment_signals(st: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    actions = op.get("recent_provider_actions") or []
    return {"recent_count": len(actions) if isinstance(actions, list) else 0, "linked_projects": len(op.get("deployment_identities") or {})}


def _repair_signals(st: dict[str, Any], repairs: Any) -> dict[str, Any]:
    active = len(repairs) if isinstance(repairs, dict) else 0
    return {"active_count": active, "tracked": bool(active)}


def _workspace_confidence_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"level": "unknown", "message": "No projects tracked"}
    low = sum(1 for r in rows if str(r.get("confidence") or "").lower() == "low")
    if low > len(rows) // 2:
        return {"level": "degraded", "message": f"{low} project(s) with low confidence"}
    return {"level": "stable", "message": f"{len(rows)} project(s) tracked"}
