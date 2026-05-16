# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Single authoritative runtime truth path for Mission Control (Phase 2 Step 10)."""

from __future__ import annotations

from typing import Any

from app.brain.brain_events import recent_brain_decisions
from app.core.config import get_settings
from app.privacy.privacy_policy import current_privacy_mode
from app.runtime.runtime_agents import (
    agent_runtime_metrics,
    list_runtime_agents,
    list_runtime_agents_history,
    office_topology,
    recover_runtime_agents_after_restart,
    sweep_expired_agents,
)
from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display
from app.services.mission_control.runtime_health_model import build_consolidated_runtime_health
from app.services.mission_control.runtime_metrics_cache import get_cached_metrics
from app.services.mission_control.runtime_lifecycle import run_runtime_lifecycle_sweeps
from app.services.mission_control.runtime_ownership import build_all_operator_traces, build_operator_trace_chains
from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot
from app.services.operator_context import build_operator_context_panel
from app.plugins.automation_packs import list_automation_packs_with_health
from app.services.aethos_differentiation import build_differentiators_summary
from app.services.privacy_operational_posture import build_privacy_operational_posture
from app.services.provider_intelligence_panel import build_provider_intelligence_panel
from app.plugins.plugin_runtime import build_plugin_health_panel
from app.marketplace.runtime_marketplace import marketplace_summary
from app.services.brain_routing_visibility import build_brain_routing_panel
from app.services.operational_intelligence import build_operational_intelligence
from app.services.runtime_governance import build_governance_audit
from app.services.operator_continuity import build_operator_continuity_truth
from app.services.workspace_runtime_intelligence import build_operational_risk, build_workspace_intelligence
from app.services.mission_control.office_operational import build_office_operational_view
from app.services.mission_control.runtime_metrics_discipline import get_runtime_discipline_metrics
from app.services.mission_control.runtime_confidence import build_runtime_confidence


def build_provider_routing_summary() -> dict[str, Any]:
    s = get_settings()
    mode = current_privacy_mode(s)
    recent = recent_brain_decisions(limit=1)
    latest = recent[0] if recent else {}
    local_first = bool(getattr(s, "aethos_local_first_enabled", False) or getattr(s, "nexa_local_first", False))
    local_only = mode.value == "local_only"
    return {
        "provider": latest.get("selected_provider"),
        "model": latest.get("selected_model"),
        "reason": latest.get("reason") or "default routing",
        "fallback_used": bool(latest.get("fallback_used")),
        "local_first": local_first,
        "local_only": local_only,
        "privacy_mode": mode.value,
        "privacy_block_active": mode.value in ("block", "local_only"),
        "task": latest.get("task"),
    }


def build_brain_visibility() -> dict[str, Any]:
    summary = build_provider_routing_summary()
    return {
        "brain": summary,
        "routing_summary": summary,
        "recent_decisions": recent_brain_decisions(limit=8),
    }


def _compute_metrics(user_id: str, ort: dict[str, Any], st: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(st.get("runtime_metrics") or {}) if isinstance(st.get("runtime_metrics"), dict) else {}
    rel = ort.get("reliability") or {}
    cont = ort.get("continuity") or {}
    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    return {
        "token_usage_estimate": metrics.get("token_usage_estimate") or metrics.get("tokens_total"),
        "task_throughput": {
            "active": ort.get("active_tasks"),
            "queued": ort.get("queued_tasks"),
            "retrying": ort.get("retrying_tasks"),
        },
        "runtime_reliability": rel,
        "runtime_continuity": cont,
        "repair_tracked_projects": len(repairs) if isinstance(repairs, dict) else 0,
        "agent_metrics": agent_runtime_metrics(),
    }


def build_runtime_truth(*, user_id: str | None = None) -> dict[str, Any]:
    """
    One authoritative runtime snapshot for agents, tasks, providers, health, plugins, repair, privacy.
    """
    recover_runtime_agents_after_restart()
    sweep_expired_agents()
    lifecycle_sweep = run_runtime_lifecycle_sweeps()
    from app.services.mission_control.runtime_event_intelligence import prune_stale_event_summaries

    prune_stale_event_summaries()
    uid = (user_id or "").strip() or None
    ort = build_orchestration_runtime_snapshot(uid)
    operator = build_operator_context_panel()
    st = load_runtime_state()
    events_display = aggregate_events_for_display(limit=48)
    health = build_consolidated_runtime_health(ort, events=events_display)
    agents_active = list_runtime_agents(include_expired=False)
    brain = build_brain_visibility()
    metrics = get_cached_metrics(uid or "_global", lambda u: _compute_metrics(u, ort, st))
    routing_summary = build_provider_routing_summary()
    plugins_panel = build_plugin_health_panel()
    privacy_posture = build_privacy_operational_posture()
    from app.services.operational_intelligence_engine import build_operational_intelligence_engine

    engine = build_operational_intelligence_engine(ort)
    operational_intel = engine

    truth: dict[str, Any] = {
        "runtime_health": health,
        "orchestrator": agents_active.get("aethos_orchestrator"),
        "runtime_agents": agents_active,
        "runtime_agents_history": list_runtime_agents_history(limit=24),
        "tasks": ort.get("tasks") or [],
        "queues": ort.get("queue_depths") or {},
        "deployments": {
            "identities": operator.get("deployment_identities") or {},
            "summary": ort.get("deployment_summary") or {},
        },
        "providers": {
            "inventory": operator.get("provider_inventory"),
            "recent_actions": (operator.get("recent_provider_actions") or [])[-12:],
            "recent_nl_actions": (operator.get("recent_nl_provider_actions") or [])[-8:],
        },
        "operator_context": operator,
        "repair": operator.get("latest_repair_contexts") or {},
        "brain_visibility": brain,
        "routing_summary": routing_summary,
        "privacy": {
            "mode": brain["brain"]["privacy_mode"],
            "local_only": brain["brain"].get("local_only"),
            "redaction_events": [e for e in events_display if e.get("category") == "privacy"],
        },
        "runtime_events": events_display,
        "runtime_events_raw_count": len(events_display),
        "runtime_metrics": metrics,
        "plugins": plugins_panel,
        "ownership_trace": build_operator_trace_chains(uid),
        "operator_traces": build_all_operator_traces(uid),
        "lifecycle_sweep": lifecycle_sweep,
        "workflows": ort.get("workflows") or {},
        "marketplace": marketplace_summary(),
        "operational_intelligence": operational_intel,
        "brain_routing_panel": build_brain_routing_panel(),
        "workspace_intelligence": build_workspace_intelligence(),
        "runtime_governance": build_governance_audit(),
        "automation_packs": list_automation_packs_with_health(),
        "privacy_posture": privacy_posture,
        "provider_intelligence": build_provider_intelligence_panel(),
        "differentiators": build_differentiators_summary(ort=ort),
        "runtime_discipline": get_runtime_discipline_metrics(),
        "readable_summaries": None,
        "runtime_workers": None,
        "runtime_confidence": None,
    }
    truth["runtime_confidence"] = build_runtime_confidence(truth, user_id=uid)
    truth["office"] = build_office_operational_view(truth, user_id=uid)
    from app.services.mission_control.runtime_summary_readability import build_readable_summaries
    from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view

    truth["readable_summaries"] = build_readable_summaries(truth)
    truth["runtime_workers"] = build_runtime_workers_view(uid)
    from app.services.agent_runtime_truth import build_agent_visibility_for_truth

    truth["agent_visibility"] = build_agent_visibility_for_truth()
    from app.services.worker_intelligence import build_worker_intelligence_truth

    wi = build_worker_intelligence_truth()
    truth["worker_memory"] = wi.get("worker_memory")
    truth["worker_deliverables"] = wi.get("worker_deliverables")
    truth["worker_continuations"] = wi.get("worker_continuations")
    truth["worker_effectiveness"] = wi.get("worker_effectiveness")
    truth["worker_summaries"] = wi.get("worker_summaries")
    from app.runtime.workspace_operational_memory import list_research_chains
    from app.services.research_continuity import build_deliverable_relationships_view

    truth["research_chains"] = list_research_chains(limit=16)
    truth["deliverable_relationships"] = build_deliverable_relationships_view(limit=32)
    truth["operational_risk"] = build_operational_risk()
    truth["operator_continuity"] = build_operator_continuity_truth()
    from app.services.enterprise_runtime_visibility import build_enterprise_runtime_panels
    from app.services.runtime_recommendations import build_runtime_recommendations

    truth["automation_pack_runtime"] = engine.get("automation_pack_runtime")
    truth["runtime_insights"] = engine.get("runtime_insights")
    truth["enterprise_operational_state"] = engine.get("enterprise_operational_state")
    truth["enterprise_runtime_panels"] = build_enterprise_runtime_panels(truth)
    truth["runtime_recommendations"] = build_runtime_recommendations(ort)
    from app.services.mission_control.runtime_cohesion import build_runtime_cohesion_bundle

    cohesion = build_runtime_cohesion_bundle(truth)
    truth["runtime_cohesion"] = cohesion
    truth["enterprise_operational_health"] = cohesion.get("enterprise_operational_health")
    truth["unified_operational_timeline"] = cohesion.get("unified_timeline")
    truth["operational_coordination"] = cohesion.get("coordination")
    truth["operational_summary"] = cohesion.get("operational_summary")
    return truth


def build_runtime_panels_from_truth(truth: dict[str, Any]) -> dict[str, Any]:
    """Derive live panels from truth — no duplicate orchestration reads."""
    brain = truth.get("brain_visibility") or {}
    return {
        "runtime_health": truth.get("runtime_health"),
        "brain_routing": brain,
        "provider_operations": {
            "inventory": (truth.get("providers") or {}).get("inventory"),
            "recent_actions": (truth.get("providers") or {}).get("recent_actions"),
            "latest_repairs": truth.get("repair"),
            "deployment_identities": (truth.get("deployments") or {}).get("identities"),
        },
        "runtime_agents": {
            "agents": truth.get("runtime_agents"),
            "history": truth.get("runtime_agents_history"),
            "metrics": (truth.get("runtime_metrics") or {}).get("agent_metrics"),
            "ownership": truth.get("ownership_trace"),
        },
        "privacy_runtime": truth.get("privacy"),
        "recovery": {
            "continuity": (truth.get("runtime_metrics") or {}).get("runtime_continuity"),
            "events": [e for e in (truth.get("runtime_events") or []) if "recover" in str(e.get("event_type") or "")],
        },
        "marketplace": truth.get("marketplace"),
        "operational_intelligence": truth.get("operational_intelligence"),
        "workspace_intelligence": truth.get("workspace_intelligence"),
        "plugin_health": truth.get("plugins"),
        "runtime_governance": truth.get("runtime_governance"),
        "automation_packs": truth.get("automation_packs"),
        "brain_routing_advanced": truth.get("brain_routing_panel"),
        "privacy_posture": truth.get("privacy_posture"),
        "provider_intelligence": truth.get("provider_intelligence"),
        "differentiators": truth.get("differentiators"),
        "office_operational": truth.get("office"),
        "runtime_discipline": truth.get("runtime_discipline"),
        "enterprise_operational_health": truth.get("enterprise_operational_health"),
        "unified_timeline": truth.get("unified_operational_timeline"),
        "operational_coordination": truth.get("operational_coordination"),
        "runtime_cohesion": truth.get("runtime_cohesion"),
    }
