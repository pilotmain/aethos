# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime scalability health, pressure, and enterprise summaries (Phase 3 Step 13)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.operational_payload_discipline import (
    build_payload_discipline_block,
    get_payload_discipline_metrics,
)
from app.services.mission_control.runtime_hydration import get_hydration_metrics
from app.services.mission_control.runtime_metrics_discipline import get_runtime_discipline_metrics


def build_runtime_scalability_health(truth: dict[str, Any]) -> dict[str, Any]:
    disc = get_runtime_discipline_metrics()
    h = get_hydration_metrics()
    scale = truth.get("runtime_scalability") or {}
    buf = int(disc.get("event_buffer_size") or 0)
    hits = int(h.get("slice_cache_hits") or 0)
    misses = int(h.get("slice_cache_misses") or 0)
    total = hits + misses
    hit_rate = round(hits / max(1, total), 4) if total else None
    pressure = _pressure_level(truth, disc)
    return {
        "status": "healthy" if pressure == "low" else ("warning" if pressure == "medium" else "elevated"),
        "operational_pressure": pressure,
        "event_buffer_size": buf,
        "bounded_deliverables": scale.get("bounded_deliverables"),
        "bounded_events": scale.get("bounded_events"),
        "slice_cache_hit_rate": hit_rate,
        "hydration_ms": h.get("last_hydration_ms"),
        "payload_within_budget": build_payload_discipline_block(truth).get("within_budget"),
    }


def build_operational_pressure(truth: dict[str, Any]) -> dict[str, Any]:
    office = truth.get("office") or {}
    pressure = office.get("pressure") if isinstance(office, dict) else {}
    disc = get_runtime_discipline_metrics()
    queues = truth.get("queues") or {}
    q_depth = sum(int(v) for v in queues.values() if isinstance(v, (int, float)))
    return {
        "queue_pressure": bool(pressure.get("queue")) if isinstance(pressure, dict) else q_depth > 10,
        "retry_pressure": bool(pressure.get("retry")) if isinstance(pressure, dict) else False,
        "deployment_pressure": bool(pressure.get("deployment")) if isinstance(pressure, dict) else False,
        "event_buffer_size": disc.get("event_buffer_size"),
        "queue_depth_total": q_depth,
        "worker_count": len((truth.get("runtime_workers") or {}).get("workers") or [])
        if isinstance(truth.get("runtime_workers"), dict)
        else 0,
        "level": _pressure_level(truth, disc),
    }


def build_runtime_query_efficiency() -> dict[str, Any]:
    disc = get_runtime_discipline_metrics()
    h = get_hydration_metrics()
    hits = int(disc.get("truth_cache_hits") or 0)
    misses = int(disc.get("truth_cache_misses") or 0)
    sh = int(h.get("slice_cache_hits") or 0)
    sm = int(h.get("slice_cache_misses") or 0)
    return {
        "truth_cache_hit_rate": disc.get("truth_cache_hit_rate"),
        "slice_cache_hit_rate": round(sh / max(1, sh + sm), 4) if (sh + sm) else None,
        "cache_reuse_rate": disc.get("truth_cache_hit_rate"),
        "last_truth_build_ms": disc.get("last_truth_build_ms"),
        "last_hydration_ms": h.get("last_hydration_ms"),
        "expensive_query_count": int((disc.get("counters") or {}).get("expensive_query") or 0)
        if isinstance(disc.get("counters"), dict)
        else 0,
        "derived_metric_reuse": sh > 0,
    }


def build_governance_scalability() -> dict[str, Any]:
    st = load_runtime_state()
    plugin = len(st.get("plugin_governance_audit") or []) if isinstance(st.get("plugin_governance_audit"), list) else 0
    prov = len(st.get("operator_provider_actions") or []) if isinstance(st.get("operator_provider_actions"), list) else 0
    ws = st.get("workspace_governance_events") or {}
    ws_n = len(ws) if isinstance(ws, dict) else 0
    return {
        "plugin_audit_entries": plugin,
        "provider_action_entries": prov,
        "workspace_governance_entries": ws_n,
        "searchable": True,
        "bounded_timeline_window": int(getattr(get_settings(), "aethos_timeline_page_max", 48)),
    }


def build_enterprise_operational_views(truth: dict[str, Any]) -> dict[str, Any]:
    health = truth.get("enterprise_operational_health") or {}
    intel = truth.get("operational_intelligence") or {}
    risk = truth.get("operational_risk") or {}
    return {
        "operational_pressure_overview": build_operational_pressure(truth),
        "deployment_stability_overview": _deployment_overview(truth),
        "provider_stability_overview": _provider_overview(truth),
        "worker_effectiveness_overview": _worker_overview(truth),
        "governance_risk_overview": {
            "risk_level": risk.get("level") or risk.get("overall"),
            "categories": (health.get("categories") or {}) if isinstance(health, dict) else {},
        },
        "runtime_scalability_overview": build_runtime_scalability_health(truth),
        "operational_responsiveness_overview": truth.get("operational_responsiveness") or {},
        "intelligence_summary": (intel.get("summaries") or intel.get("summary")) if isinstance(intel, dict) else None,
    }


def _pressure_level(truth: dict[str, Any], disc: dict[str, Any]) -> str:
    buf = int(disc.get("event_buffer_size") or 0)
    limit = int(getattr(get_settings(), "aethos_runtime_event_buffer_limit", 500))
    if buf > limit * 0.85:
        return "high"
    office = truth.get("office") or {}
    p = office.get("pressure") if isinstance(office, dict) else {}
    if isinstance(p, dict) and any(p.get(k) for k in ("queue", "retry", "deployment")):
        return "medium"
    return "low"


def _deployment_overview(truth: dict[str, Any]) -> dict[str, Any]:
    dep = truth.get("deployments") or {}
    summary = dep.get("summary") if isinstance(dep, dict) else {}
    return {"summary": summary, "identity_count": len((dep.get("identities") or {})) if isinstance(dep, dict) else 0}


def _provider_overview(truth: dict[str, Any]) -> dict[str, Any]:
    prov = truth.get("providers") or {}
    inv = prov.get("inventory") if isinstance(prov, dict) else {}
    return {
        "recent_actions": len((prov.get("recent_actions") or [])) if isinstance(prov, dict) else 0,
        "inventory_size": len((inv.get("providers") or {})) if isinstance(inv, dict) else 0,
    }


def _worker_overview(truth: dict[str, Any]) -> dict[str, Any]:
    rw = truth.get("runtime_workers") or {}
    eff = truth.get("worker_effectiveness") or {}
    return {
        "active_count": rw.get("active_count") if isinstance(rw, dict) else 0,
        "worker_count": len((rw.get("workers") or [])) if isinstance(rw, dict) else 0,
        "effectiveness": eff if isinstance(eff, dict) else {},
    }


def build_worker_pressure_metrics() -> dict[str, Any]:
    st = load_runtime_state()
    s = get_settings()
    dlim = int(getattr(s, "aethos_worker_deliverable_limit", 200))
    clim = int(getattr(s, "aethos_worker_continuation_limit", 48))
    deliverables = st.get("worker_deliverables") or {}
    continuations = st.get("worker_continuations") or {}
    dn = len(deliverables) if isinstance(deliverables, dict) else 0
    cn = len(continuations) if isinstance(continuations, dict) else 0
    return {
        "worker_deliverable_pressure": round(dn / max(1, dlim), 4),
        "worker_continuation_pressure": round(cn / max(1, clim), 4),
        "worker_memory_pressure": round(dn / max(1, dlim * 0.5), 4),
        "worker_summary_efficiency": 1.0 if dn <= dlim * 0.75 else 0.6,
    }
