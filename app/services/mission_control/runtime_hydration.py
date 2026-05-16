# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Incremental runtime truth hydration and slice cache (Phase 3 Step 12)."""

from __future__ import annotations

import time
from typing import Any, Callable

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_SLICE_TTL_DEFAULT = 15.0
_FULL_TTL_DEFAULT = 30.0
_MAINTENANCE_INTERVAL_DEFAULT = 60.0
_MAX_SLICE_CACHE_KEYS = 8


def _settings() -> tuple[float, float, float]:
    from app.core.config import get_settings

    s = get_settings()
    full = float(getattr(s, "aethos_truth_cache_ttl_sec", _FULL_TTL_DEFAULT))
    slice_ttl = float(getattr(s, "aethos_truth_slice_ttl_sec", _SLICE_TTL_DEFAULT))
    maint = float(getattr(s, "aethos_truth_maintenance_interval_sec", _MAINTENANCE_INTERVAL_DEFAULT))
    return full, slice_ttl, maint


def get_hydration_metrics() -> dict[str, Any]:
    st = load_runtime_state()
    h = st.get("hydration_metrics") or {}
    return dict(h) if isinstance(h, dict) else {}


def record_hydration_metric(**fields: Any) -> None:
    st = load_runtime_state()
    h = st.setdefault("hydration_metrics", {})
    if isinstance(h, dict):
        h.update({k: v for k, v in fields.items() if v is not None})
        h["updated_at"] = utc_now_iso()
    save_runtime_state(st)


def invalidate_slice_cache(user_id: str | None = None, slice_name: str | None = None) -> None:
    from app.services.mission_control.runtime_truth_cache import invalidate_runtime_truth_cache

    st = load_runtime_state()
    cache = st.get("mc_runtime_slice_cache") or {}
    if not isinstance(cache, dict):
        return
    key = (user_id or "").strip() or "_global"
    if slice_name:
        bucket = cache.get(key)
        if isinstance(bucket, dict):
            bucket.pop(slice_name, None)
    else:
        cache.pop(key, None)
    st["mc_runtime_slice_cache"] = cache
    save_runtime_state(st)
    invalidate_runtime_truth_cache(user_id)
    record_hydration_metric(invalidation_rate=int(get_hydration_metrics().get("invalidation_rate") or 0) + 1)


def get_cached_slice(
    slice_name: str,
    user_id: str | None,
    builder: Callable[[], dict[str, Any]],
    *,
    ttl_sec: float | None = None,
) -> dict[str, Any]:
    """Slice-level cache — sub-second when warm."""
    _, default_ttl, _ = _settings()
    ttl = ttl_sec if ttl_sec is not None else default_ttl
    st = load_runtime_state()
    cache = st.setdefault("mc_runtime_slice_cache", {})
    if not isinstance(cache, dict):
        cache = {}
        st["mc_runtime_slice_cache"] = cache
    ukey = (user_id or "").strip() or "_global"
    bucket = cache.setdefault(ukey, {})
    if not isinstance(bucket, dict):
        bucket = {}
        cache[ukey] = bucket
    now = time.monotonic()
    entry = bucket.get(slice_name)
    if isinstance(entry, dict):
        ts = float(entry.get("_mono_ts") or 0)
        if now - ts < ttl and isinstance(entry.get("data"), dict):
            record_hydration_metric(
                slice_cache_hits=int(get_hydration_metrics().get("slice_cache_hits") or 0) + 1,
            )
            return dict(entry["data"])
    t0 = time.monotonic()
    data = builder()
    elapsed = (time.monotonic() - t0) * 1000.0
    bucket[slice_name] = {
        "data": data,
        "_mono_ts": now,
        "built_at": utc_now_iso(),
        "duration_ms": round(elapsed, 2),
    }
    if len(cache) > _MAX_SLICE_CACHE_KEYS:
        oldest = min(cache.items(), key=lambda kv: float((kv[1] or {}).get("_mono_ts") or 0) if isinstance(kv[1], dict) else 0)
        cache.pop(oldest[0], None)
    record_hydration_metric(
        slice_cache_misses=int(get_hydration_metrics().get("slice_cache_misses") or 0) + 1,
        last_slice_build_ms=round(elapsed, 2),
        last_slice_name=slice_name,
    )
    save_runtime_state(st)
    return data


def _maybe_run_maintenance() -> None:
    _, _, maint_interval = _settings()
    st = load_runtime_state()
    h = st.setdefault("hydration_metrics", {})
    last = float(h.get("last_maintenance_mono") or 0) if isinstance(h, dict) else 0
    now = time.monotonic()
    if now - last < maint_interval:
        return
    from app.runtime.runtime_agents import recover_runtime_agents_after_restart, sweep_expired_agents
    from app.services.mission_control.runtime_lifecycle import run_runtime_lifecycle_sweeps
    from app.services.mission_control.runtime_event_intelligence import prune_stale_event_summaries
    from app.services.mission_control.runtime_memory_optimization import run_memory_optimization_sweep

    recover_runtime_agents_after_restart()
    sweep_expired_agents()
    run_runtime_lifecycle_sweeps()
    prune_stale_event_summaries()
    run_memory_optimization_sweep()
    if isinstance(h, dict):
        h["last_maintenance_mono"] = now
        h["last_maintenance_at"] = utc_now_iso()
    save_runtime_state(st)


def _build_core_slice(user_id: str | None) -> dict[str, Any]:
    from app.runtime.runtime_agents import list_runtime_agents, list_runtime_agents_history
    from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot
    from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display
    from app.services.mission_control.runtime_health_model import build_consolidated_runtime_health
    from app.services.operator_context import build_operator_context_panel
    from app.services.mission_control.runtime_truth import (
        build_brain_visibility,
        build_provider_routing_summary,
        _compute_metrics,
    )
    from app.services.mission_control.runtime_metrics_cache import get_cached_metrics
    from app.plugins.plugin_runtime import build_plugin_health_panel
    from app.services.privacy_operational_posture import build_privacy_operational_posture
    from app.marketplace.runtime_marketplace import marketplace_summary
    from app.services.brain_routing_visibility import build_brain_routing_panel
    from app.services.aethos_differentiation import build_differentiators_summary
    from app.services.mission_control.runtime_metrics_discipline import get_runtime_discipline_metrics

    uid = (user_id or "").strip() or None
    ort = build_orchestration_runtime_snapshot(uid)
    operator = build_operator_context_panel()
    st = load_runtime_state()
    events_display = aggregate_events_for_display(limit=32)
    health = build_consolidated_runtime_health(ort, events=events_display)
    agents_active = list_runtime_agents(include_expired=False)
    brain = build_brain_visibility()
    metrics = get_cached_metrics(uid or "_global", lambda u: _compute_metrics(u, ort, st))
    routing_summary = build_provider_routing_summary()
    raw_tasks = ort.get("tasks") or []
    if isinstance(raw_tasks, dict):
        tasks = list(raw_tasks.values())[:48]
    elif isinstance(raw_tasks, list):
        tasks = raw_tasks[:48]
    else:
        tasks = []
    return {
        "runtime_health": health,
        "orchestrator": agents_active.get("aethos_orchestrator"),
        "runtime_agents": agents_active,
        "runtime_agents_history": list_runtime_agents_history(limit=16),
        "tasks": tasks,
        "queues": ort.get("queue_depths") or {},
        "deployments": {
            "identities": operator.get("deployment_identities") or {},
            "summary": ort.get("deployment_summary") or {},
        },
        "providers": {
            "inventory": operator.get("provider_inventory"),
            "recent_actions": (operator.get("recent_provider_actions") or [])[-8:],
            "recent_nl_actions": (operator.get("recent_nl_provider_actions") or [])[-6:],
        },
        "operator_context": operator,
        "repair": operator.get("latest_repair_contexts") or {},
        "brain_visibility": brain,
        "routing_summary": routing_summary,
        "privacy": {
            "mode": brain["brain"]["privacy_mode"],
            "local_only": brain["brain"].get("local_only"),
            "redaction_events": [e for e in events_display if e.get("category") == "privacy"][:12],
        },
        "runtime_events": events_display,
        "runtime_events_raw_count": len(events_display),
        "runtime_metrics": metrics,
        "plugins": build_plugin_health_panel(),
        "workflows": ort.get("workflows") or {},
        "marketplace": marketplace_summary(),
        "privacy_posture": build_privacy_operational_posture(),
        "brain_routing_panel": build_brain_routing_panel(),
        "provider_intelligence": {},
        "differentiators": build_differentiators_summary(ort=ort),
        "runtime_discipline": get_runtime_discipline_metrics(),
        "_ort": ort,
    }


def _build_workers_slice(user_id: str | None, core: dict[str, Any]) -> dict[str, Any]:
    from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view
    from app.services.mission_control.office_operational import build_office_operational_view
    from app.services.agent_runtime_truth import build_agent_visibility_for_truth

    uid = (user_id or "").strip() or None
    partial = {**core}
    partial["runtime_workers"] = build_runtime_workers_view(uid)
    partial["office"] = build_office_operational_view(partial, user_id=uid)
    return {
        "runtime_workers": partial.get("runtime_workers"),
        "office": partial.get("office"),
        "agent_visibility": build_agent_visibility_for_truth(),
    }


def _build_intelligence_slice(user_id: str | None, core: dict[str, Any]) -> dict[str, Any]:
    from app.services.operational_intelligence_engine import build_operational_intelligence_engine
    from app.services.runtime_recommendations import build_runtime_recommendations
    from app.services.provider_intelligence_panel import build_provider_intelligence_panel

    ort = core.get("_ort") or {}
    engine = build_operational_intelligence_engine(ort)
    return {
        "operational_intelligence": engine,
        "runtime_recommendations": build_runtime_recommendations(ort),
        "provider_intelligence": build_provider_intelligence_panel(),
        "automation_pack_runtime": engine.get("automation_pack_runtime"),
        "runtime_insights": engine.get("runtime_insights"),
        "enterprise_operational_state": engine.get("enterprise_operational_state"),
    }


def _build_workspace_slice() -> dict[str, Any]:
    from app.services.workspace_runtime_intelligence import build_operational_risk, build_workspace_intelligence
    from app.services.operator_continuity import build_operator_continuity_truth
    from app.runtime.workspace_operational_memory import list_research_chains
    from app.services.research_continuity import build_deliverable_relationships_view

    return {
        "workspace_intelligence": build_workspace_intelligence(),
        "operational_risk": build_operational_risk(),
        "operator_continuity": build_operator_continuity_truth(),
        "research_chains": list_research_chains(limit=12),
        "deliverable_relationships": build_deliverable_relationships_view(limit=24),
    }


def _build_worker_memory_slice() -> dict[str, Any]:
    from app.services.worker_intelligence import build_worker_intelligence_truth

    wi = build_worker_intelligence_truth()
    return {
        "worker_memory": wi.get("worker_memory"),
        "worker_deliverables": (wi.get("worker_deliverables") or [])[:24],
        "worker_continuations": (wi.get("worker_continuations") or [])[:16],
        "worker_effectiveness": wi.get("worker_effectiveness"),
        "worker_summaries": (wi.get("worker_summaries") or [])[:16],
    }


def _build_governance_slice() -> dict[str, Any]:
    from app.services.runtime_governance import build_governance_audit
    from app.plugins.automation_packs import list_automation_packs_with_health

    return {
        "runtime_governance": build_governance_audit(),
        "automation_packs": list_automation_packs_with_health(),
    }


def _build_derived_slice(user_id: str | None, truth: dict[str, Any]) -> dict[str, Any]:
    from app.services.mission_control.runtime_confidence import build_runtime_confidence
    from app.services.mission_control.runtime_summary_readability import build_readable_summaries
    from app.services.enterprise_runtime_visibility import build_enterprise_runtime_panels
    from app.services.mission_control.runtime_cohesion import build_runtime_cohesion_bundle

    uid = (user_id or "").strip() or None
    t = dict(truth)
    t.pop("_ort", None)
    conf = build_runtime_confidence(t, user_id=uid)
    panels = build_enterprise_runtime_panels(t)
    cohesion = build_runtime_cohesion_bundle(t)
    return {
        "runtime_confidence": conf,
        "readable_summaries": build_readable_summaries(t),
        "enterprise_runtime_panels": panels,
        "runtime_cohesion": cohesion,
        "enterprise_operational_health": cohesion.get("enterprise_operational_health"),
        "unified_operational_timeline": cohesion.get("unified_timeline"),
        "operational_coordination": cohesion.get("coordination"),
        "operational_summary": cohesion.get("operational_summary"),
    }


def hydrate_runtime_truth_incremental(*, user_id: str | None = None) -> dict[str, Any]:
    """Assemble truth from cached slices — avoids full monolithic rebuild when slices are warm."""
    t0 = time.monotonic()
    _maybe_run_maintenance()
    uid = user_id

    core = get_cached_slice("core", uid, lambda: _build_core_slice(uid))
    workers = get_cached_slice("workers", uid, lambda: _build_workers_slice(uid, core))
    intelligence = get_cached_slice("intelligence", uid, lambda: _build_intelligence_slice(uid, core))
    workspace = get_cached_slice("workspace", uid, _build_workspace_slice)
    worker_mem = get_cached_slice("worker_memory", uid, _build_worker_memory_slice)
    governance = get_cached_slice("governance", uid, _build_governance_slice)

    truth: dict[str, Any] = {}
    for part in (core, workers, intelligence, workspace, worker_mem, governance):
        for k, v in part.items():
            if not k.startswith("_"):
                truth[k] = v

    from app.services.mission_control.runtime_ownership import build_all_operator_traces, build_operator_trace_chains

    truth["ownership_trace"] = build_operator_trace_chains(uid)
    truth["operator_traces"] = build_all_operator_traces(uid)
    truth["lifecycle_sweep"] = {}

    derived = get_cached_slice("derived", uid, lambda: _build_derived_slice(uid, truth))
    truth.update(derived)

    elapsed = (time.monotonic() - t0) * 1000.0
    from app.services.mission_control.runtime_metrics_discipline import approx_payload_bytes

    payload_bytes = approx_payload_bytes(truth)
    record_hydration_metric(
        last_hydration_ms=round(elapsed, 2),
        last_payload_bytes=payload_bytes,
        hydration_mode="incremental",
    )
    truth["runtime_performance"] = build_runtime_performance_block(elapsed, payload_bytes)
    truth["hydration_metrics"] = get_hydration_metrics()
    truth["operational_responsiveness"] = {
        "target_cached_read_ms": 500,
        "last_hydration_ms": round(elapsed, 2),
        "mode": "incremental_slices",
    }
    truth["runtime_scalability"] = {
        "slice_count": 7,
        "bounded_deliverables": len(truth.get("worker_deliverables") or []),
        "bounded_events": len(truth.get("runtime_events") or []),
    }
    from app.services.mission_control.operational_payload_discipline import (
        build_payload_discipline_block,
        summarize_truth_payload,
    )
    from app.services.mission_control.runtime_scalability import (
        build_enterprise_operational_views,
        build_governance_scalability,
        build_operational_pressure,
        build_runtime_query_efficiency,
        build_runtime_scalability_health,
    )

    truth = summarize_truth_payload(truth)
    truth["payload_discipline"] = build_payload_discipline_block(truth)
    truth["runtime_scalability_health"] = build_runtime_scalability_health(truth)
    truth["operational_pressure"] = build_operational_pressure(truth)
    truth["runtime_query_efficiency"] = build_runtime_query_efficiency()
    truth["governance_scalability"] = build_governance_scalability()
    truth["enterprise_operational_views"] = build_enterprise_operational_views(truth)
    from app.services.mission_control.execution_visibility import (
        build_execution_chains,
        build_execution_governance,
        build_execution_trace_health,
        build_execution_visibility,
    )
    from app.services.mission_control.enterprise_trust_views import build_enterprise_trust_panels
    from app.services.mission_control.governance_timeline_unified import build_unified_governance_timeline
    from app.services.mission_control.operational_explainability import build_operational_explainability
    from app.services.mission_control.operational_trust import build_operational_trust_model
    from app.services.mission_control.runtime_escalations import (
        build_escalation_history,
        build_escalation_visibility,
        build_runtime_escalations,
    )
    from app.services.mission_control.worker_accountability import (
        build_worker_accountability,
        build_worker_governance,
        build_worker_operational_quality,
    )

    truth["runtime_escalations"] = build_runtime_escalations(truth)
    truth["escalation_visibility"] = build_escalation_visibility(truth)
    truth["escalation_history"] = build_escalation_history(truth)
    truth["execution_visibility"] = build_execution_visibility(truth, user_id=uid)
    truth["execution_chains"] = build_execution_chains(truth, user_id=uid)
    truth["execution_governance"] = build_execution_governance(truth)
    truth["execution_trace_health"] = build_execution_trace_health(truth)
    trust = build_operational_trust_model(truth)
    truth.update(trust)
    truth["worker_accountability"] = build_worker_accountability(truth, user_id=uid)
    truth["worker_governance"] = build_worker_governance(truth)
    truth["worker_operational_quality"] = build_worker_operational_quality(truth)
    truth["operational_explainability"] = build_operational_explainability(truth)
    truth["enterprise_trust_panels"] = build_enterprise_trust_panels(truth)
    truth["unified_operational_timeline"] = build_unified_governance_timeline(truth, limit=40)
    from app.services.runtime_recommendations import enrich_recommendations_with_trust

    enrich_recommendations_with_trust(truth)
    from app.services.mission_control.enterprise_operator_experience import (
        build_enterprise_operator_experience,
        build_enterprise_runtime_views,
        build_runtime_overview,
    )
    from app.services.mission_control.governance_experience import build_governance_experience
    from app.services.mission_control.operational_calmness import build_operational_quality, build_runtime_calmness
    from app.services.mission_control.operational_narratives import build_operational_narratives
    from app.services.mission_control.runtime_identity import build_runtime_identity
    from app.services.mission_control.runtime_storytelling import build_runtime_stories
    from app.services.mission_control.worker_runtime_cohesion import (
        build_unified_worker_state,
        build_worker_operational_identity,
        build_worker_runtime_cohesion,
    )

    truth["runtime_identity"] = build_runtime_identity(truth)
    truth["operational_narratives"] = build_operational_narratives(truth)
    truth["runtime_stories"] = build_runtime_stories(truth)
    truth["runtime_calmness"] = build_runtime_calmness(truth)
    truth["operational_quality"] = build_operational_quality(truth)
    truth["governance_experience"] = build_governance_experience(truth)
    truth["unified_worker_state"] = build_unified_worker_state(truth, user_id=uid)
    truth["worker_operational_identity"] = build_worker_operational_identity(truth)
    truth["worker_runtime_cohesion"] = build_worker_runtime_cohesion(truth, user_id=uid)
    truth["enterprise_operator_experience"] = build_enterprise_operator_experience(truth, user_id=uid)
    truth["enterprise_runtime_views"] = build_enterprise_runtime_views(truth)
    truth["runtime_overview"] = build_runtime_overview(truth)
    from app.services.mission_control.enterprise_readiness import build_enterprise_readiness
    from app.services.mission_control.governance_completion import (
        build_escalation_operational_summary,
        build_governance_operational_summary,
        build_runtime_accountability_summary,
    )
    from app.services.mission_control.operational_calmness_lock import build_calmness_lock
    from app.services.mission_control.operational_performance_completion import (
        build_operational_performance_completion,
    )
    from app.services.mission_control.production_hardening import verify_production_bounds
    from app.services.mission_control.runtime_cleanup_completion import build_cleanup_completion
    from app.services.mission_control.runtime_discipline_completion import (
        build_operational_signal_health,
        build_runtime_discipline_completion,
        build_simplification_progress,
    )
    from app.services.mission_control.runtime_truth_lock import build_truth_lock_status

    truth.update(build_enterprise_readiness(truth))
    truth["enterprise_readiness"] = build_enterprise_readiness(truth)
    truth["truth_lock"] = build_truth_lock_status(truth)
    truth["production_hardening"] = verify_production_bounds(truth)
    truth["runtime_discipline_completion"] = build_runtime_discipline_completion(truth)
    truth["simplification_progress"] = build_simplification_progress()
    truth["operational_signal_health"] = build_operational_signal_health(truth)
    truth["operational_performance_completion"] = build_operational_performance_completion(truth)
    truth["calmness_lock"] = build_calmness_lock(truth)
    truth["governance_operational_summary"] = build_governance_operational_summary(truth)
    truth["runtime_accountability_summary"] = build_runtime_accountability_summary(truth)
    truth["escalation_operational_summary"] = build_escalation_operational_summary(truth)
    truth["cleanup_completion"] = build_cleanup_completion()
    return truth


def build_runtime_performance_block(hydration_ms: float, payload_bytes: int) -> dict[str, Any]:
    h = get_hydration_metrics()
    hits = int(h.get("slice_cache_hits") or 0)
    misses = int(h.get("slice_cache_misses") or 0)
    total = hits + misses
    return {
        "hydration_latency_ms": round(hydration_ms, 2),
        "payload_bytes": payload_bytes,
        "cache_hit_rate": round(hits / max(1, total), 4) if total else None,
        "slice_cache_hits": hits,
        "slice_cache_misses": misses,
        "truth_build_duration_ms": h.get("last_truth_build_ms"),
    }


def build_incremental_timeline(*, limit: int = 40, severity: str | None = None) -> dict[str, Any]:
    from app.services.mission_control.runtime_timeline_hydration import build_incremental_timeline as _build

    return _build(limit=limit, severity=severity)


def get_lightweight_slice(slice_name: str, user_id: str | None = None) -> dict[str, Any]:
    """API fast path — single slice without full truth assembly."""
    builders: dict[str, Callable[[], dict[str, Any]]] = {
        "workers": lambda: _build_workers_slice(user_id, get_cached_slice("core", user_id, lambda: _build_core_slice(user_id))),
        "deployments": lambda: {
            "deployments": get_cached_slice("core", user_id, lambda: _build_core_slice(user_id)).get("deployments"),
            "repair": get_cached_slice("core", user_id, lambda: _build_core_slice(user_id)).get("repair"),
        },
        "providers": lambda: {"providers": get_cached_slice("core", user_id, lambda: _build_core_slice(user_id)).get("providers")},
        "governance": _build_governance_slice,
        "recommendations": lambda: _build_intelligence_slice(
            user_id, get_cached_slice("core", user_id, lambda: _build_core_slice(user_id))
        ),
        "health": lambda: {
            "enterprise_operational_health": get_cached_slice(
                "derived",
                user_id,
                lambda: _build_derived_slice(
                    user_id,
                    {**get_cached_slice("core", user_id, lambda: _build_core_slice(user_id))},
                ),
            ).get("enterprise_operational_health"),
            "runtime_health": get_cached_slice("core", user_id, lambda: _build_core_slice(user_id)).get("runtime_health"),
        },
        "intelligence": lambda: _build_intelligence_slice(
            user_id, get_cached_slice("core", user_id, lambda: _build_core_slice(user_id))
        ),
        "continuity": lambda: _build_workspace_slice(),
        "timeline": lambda: build_incremental_timeline(limit=40),
    }
    fn = builders.get(slice_name)
    if not fn:
        return {}
    return get_cached_slice(f"api_{slice_name}", user_id, fn, ttl_sec=10.0)
