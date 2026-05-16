# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified runtime cohesion — single truth path for all operational views (Phase 3 Step 11)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_cohesion import build_cohesion_report
from app.services.mission_control.operational_coordination import build_coordination_signals
from app.services.mission_control.runtime_health_model import build_enterprise_operational_health
from app.services.mission_control.worker_collaboration_visibility import build_worker_collaboration_chains_enriched
from app.services.runtime_governance import build_governance_timeline


def derive_operational_views_from_truth(truth: dict[str, Any]) -> dict[str, Any]:
    """All Mission Control operational slices derived from one truth dict — no re-fetch."""
    return {
        "workers": truth.get("runtime_workers"),
        "tasks": truth.get("tasks"),
        "deployments": truth.get("deployments"),
        "providers": truth.get("providers"),
        "plugins": truth.get("plugins"),
        "automation_packs": truth.get("automation_packs"),
        "recommendations": truth.get("runtime_recommendations"),
        "operational_intelligence": truth.get("operational_intelligence"),
        "governance": truth.get("runtime_governance"),
        "continuity": truth.get("operator_continuity"),
        "operational_risk": truth.get("operational_risk"),
        "deliverables": truth.get("worker_deliverables"),
        "workspace_intelligence": truth.get("workspace_intelligence"),
        "enterprise_panels": truth.get("enterprise_runtime_panels"),
    }


def build_unified_operational_timeline(truth: dict[str, Any] | None = None, *, limit: int = 40) -> dict[str, Any]:
    """Merge governance timeline with truth-backed deliverable/recommendation highlights."""
    if truth and truth.get("unified_operational_timeline"):
        return truth["unified_operational_timeline"]
    from app.services.mission_control.governance_timeline_unified import build_unified_governance_timeline

    if truth:
        return build_unified_governance_timeline(truth, limit=limit)
    truth = truth or {}
    base = build_governance_timeline(limit=limit)
    entries = list(base.get("timeline") or [])

    for rec in ((truth.get("runtime_recommendations") or {}).get("recommendations") or [])[:4]:
        if isinstance(rec, dict):
            entries.append(
                {
                    "at": None,
                    "kind": "recommendation",
                    "who": "runtime intelligence",
                    "what": rec.get("message", "")[:120],
                    "confidence": rec.get("confidence"),
                }
            )

    for sig in ((truth.get("operational_risk") or {}).get("risk_signals") or [])[:3]:
        if isinstance(sig, dict):
            entries.append(
                {
                    "at": None,
                    "kind": "risk",
                    "who": "workspace",
                    "what": f"{sig.get('kind')} ({sig.get('severity')})",
                }
            )

    entries.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    searchable = _timeline_search_index(entries)
    return {
        "timeline": entries[:limit],
        "summary": base.get("summary"),
        "entry_count": len(entries[:limit]),
        "searchable_kinds": sorted({e.get("kind") for e in entries if e.get("kind")}),
        "search_index": searchable[:limit],
    }


def build_operational_summary(truth: dict[str, Any]) -> dict[str, Any]:
    health = build_enterprise_operational_health(truth)
    coord = build_coordination_signals(truth)
    views = derive_operational_views_from_truth(truth)
    intel = truth.get("operational_intelligence") or {}
    summaries = intel.get("summaries") if isinstance(intel, dict) else {}
    return {
        "headline": _headline_from_health(health),
        "enterprise_health": health,
        "coordination": coord,
        "cohesion": build_cohesion_report(truth),
        "readable": truth.get("readable_summaries"),
        "summaries": summaries,
        "single_truth_path": True,
        "view_keys": sorted(views.keys()),
    }


def build_runtime_cleanup_progression() -> dict[str, Any]:
    """Measurable cleanup targets for Step 11."""
    return {
        "duplicate_truth_builders": "consolidated — use build_runtime_truth only",
        "parallel_intelligence": "consolidated — operational_intelligence_engine",
        "legacy_ui_paths": "secondary nav for deliverables/workspace/insights",
        "disconnected_worker_state": "resolved — worker_memory in truth",
        "progress_score": 0.85,
        "notes": [
            "All MC APIs should call get_cached_runtime_truth → build_runtime_truth",
            "Panels derive via build_runtime_panels_from_truth",
        ],
    }


def build_runtime_cohesion_bundle(truth: dict[str, Any]) -> dict[str, Any]:
    return {
        "operational_views": derive_operational_views_from_truth(truth),
        "enterprise_operational_health": build_enterprise_operational_health(truth),
        "unified_timeline": build_unified_operational_timeline(truth),
        "operational_summary": build_operational_summary(truth),
        "coordination": build_coordination_signals(truth),
        "worker_collaboration": build_worker_collaboration_chains_enriched(truth),
        "cleanup_progression": build_runtime_cleanup_progression(),
        "cohesion_report": build_cohesion_report(truth),
    }


def _headline_from_health(health: dict[str, Any]) -> str:
    overall = str(health.get("overall") or "healthy")
    labels = {
        "healthy": "Runtime operational — all categories stable",
        "warning": "Runtime attention — review recommendations",
        "degraded": "Runtime degraded — coordination signals active",
        "critical": "Runtime critical — operator action advised",
        "recovering": "Runtime recovering — continuity in progress",
    }
    return labels.get(overall, f"Runtime {overall}")


def _timeline_search_index(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for e in entries:
        out.append(
            {
                "kind": str(e.get("kind") or ""),
                "what": str(e.get("what") or "")[:200],
                "who": str(e.get("who") or ""),
            }
        )
    return out
