# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise runtime confidence and commercial readiness summaries (Phase 3 Step 5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.operator_ownership import build_operator_ownership_summary
from app.services.mission_control.runtime_event_intelligence import list_normalized_events


def build_runtime_confidence(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Top-level trust surface: can operators trust this runtime right now?"""
    st = load_runtime_state()
    health = truth.get("runtime_health") or {}
    metrics = truth.get("runtime_metrics") or {}
    rel = metrics.get("runtime_reliability") or {}
    cont = metrics.get("runtime_continuity") or {}
    plugins = truth.get("plugins") or {}
    status = _confidence_health(health)
    recovery_active = int(cont.get("restart_recovery_attempts") or 0) > int(
        cont.get("restart_recovery_successes") or 0
    )
    return {
        "runtime_confidence": {
            "health": status,
            "uptime_hours": _uptime_hours(st),
            "restart_count": int((st.get("runtime_metrics") or {}).get("runtime_boot_count") or 0)
            or int((st.get("runtime_stability") or {}).get("restart_cycles") or 0),
            "active_recoveries": 1 if recovery_active else 0,
            "provider_failures_24h": _count_category_24h("provider", fail_only=True),
            "plugin_failures_24h": _count_category_24h("plugin", fail_only=True),
        },
        "operational_stability": build_operational_stability(truth),
        "provider_reliability": build_provider_reliability(truth, st),
        "repair_confidence": build_repair_confidence(truth),
        "deployment_confidence": build_deployment_confidence(truth, st),
        "brain_routing_confidence": build_brain_routing_confidence(truth),
        "marketplace_stability": build_marketplace_operational_stability(truth),
        "runtime_cost": build_runtime_cost_visibility(truth),
        "onboarding": build_operator_onboarding_visibility(truth, user_id=user_id),
        "ownership": build_operator_ownership_summary(truth, user_id=user_id),
        "scalability": _scalability_from_discipline(truth.get("runtime_discipline") or {}),
    }


def _confidence_health(health: dict[str, Any]) -> str:
    st = str(health.get("status") or "healthy")
    if health.get("recovery_active"):
        return "recovering"
    if st in ("healthy", "warning", "degraded", "critical", "recovering"):
        return st
    return "healthy"


def _uptime_hours(st: dict[str, Any]) -> float:
    started = st.get("last_started_at") or st.get("created_at")
    if not started:
        return 0.0
    try:
        ts = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return round(max(0.0, delta.total_seconds() / 3600.0), 2)
    except (TypeError, ValueError):
        return 0.0


def _count_category_24h(category: str, *, fail_only: bool = False) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    n = 0
    for row in list_normalized_events(limit=400):
        if str(row.get("category") or "") != category:
            continue
        if fail_only and str(row.get("severity") or "") not in ("error", "critical", "warning"):
            continue
        ts = row.get("timestamp")
        if not ts:
            n += 1
            continue
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if t >= cutoff:
                n += 1
        except (TypeError, ValueError):
            n += 1
    return n


def build_operational_stability(truth: dict[str, Any]) -> dict[str, Any]:
    health = truth.get("runtime_health") or {}
    intel = truth.get("operational_intelligence") or {}
    return {
        "status": health.get("status"),
        "queue_pressure": health.get("queue_pressure"),
        "retry_pressure": health.get("retry_pressure"),
        "deployment_pressure": health.get("deployment_pressure"),
        "recovery_active": health.get("recovery_active"),
        "insight_count": len(intel.get("insights") or []),
        "summary": _stability_sentence(health, intel),
    }


def _stability_sentence(health: dict[str, Any], intel: dict[str, Any]) -> str:
    st = health.get("status") or "healthy"
    n = len(intel.get("insights") or [])
    if st == "healthy" and n == 0:
        return "Runtime is stable with no active warnings."
    if st == "recovering" or health.get("recovery_active"):
        return "Runtime is recovering from a recent disruption."
    return f"Runtime is {st}" + (f" with {n} operational insight(s)." if n else ".")


def build_provider_reliability(truth: dict[str, Any], st: dict[str, Any]) -> dict[str, Any]:
    inv = (truth.get("providers") or {}).get("inventory") or {}
    actions = (truth.get("providers") or {}).get("recent_actions") or []
    auth = (truth.get("provider_intelligence") or {}).get("auth_status") or {}
    failures = _count_category_24h("provider", fail_only=True)
    deploy_fail = sum(
        1
        for e in list_normalized_events(limit=200)
        if e.get("category") == "deployment" and str(e.get("severity")) in ("error", "critical")
    )
    providers: list[dict[str, Any]] = []
    if isinstance(inv, dict):
        for pid, row in list(inv.items())[:16]:
            configured = True
            if isinstance(row, dict):
                configured = bool(row.get("configured") or row.get("available"))
            auth_row = auth.get(str(pid)) if isinstance(auth, dict) else {}
            providers.append(
                {
                    "provider": pid,
                    "healthy": configured and failures == 0,
                    "configured": configured,
                    "auth_ok": bool((auth_row or {}).get("configured", configured)),
                }
            )
    unstable = [p["provider"] for p in providers if not p.get("healthy")]
    return {
        "providers": providers,
        "unstable_providers": unstable,
        "provider_failures_24h": failures,
        "deployment_failures_24h": deploy_fail,
        "recent_action_count": len(actions),
        "summary": (
            "All configured providers look healthy."
            if not unstable
            else f"Unstable: {', '.join(unstable[:4])}"
        ),
    }


def build_repair_confidence(truth: dict[str, Any]) -> dict[str, Any]:
    intel = truth.get("operational_intelligence") or {}
    rate = intel.get("repair_success_rate")
    tracked = intel.get("repair_tracked") or 0
    repairs = truth.get("repair") or {}
    return {
        "tracked_projects": tracked,
        "success_rate": rate,
        "confidence": "high" if rate is None or rate >= 0.7 else "low" if rate < 0.5 else "medium",
        "summary": (
            f"Repair confidence high ({rate:.0%} success)"
            if isinstance(rate, (int, float)) and rate >= 0.7
            else f"{len(repairs) if isinstance(repairs, dict) else 0} repair context(s) tracked"
        ),
    }


def build_deployment_confidence(truth: dict[str, Any], st: dict[str, Any]) -> dict[str, Any]:
    m = st.get("runtime_metrics") or {}
    started = int(m.get("deployment_started_total") or 0)
    failed = int(m.get("deployment_failed_total") or 0)
    completed = int(m.get("deployment_completed_total") or 0)
    rate = completed / max(1, started) if started else 1.0
    return {
        "deployments_started": started,
        "deployments_failed": failed,
        "deployments_completed": completed,
        "success_rate": round(rate, 3),
        "confidence": "high" if rate >= 0.85 and failed < 3 else "medium" if rate >= 0.6 else "low",
        "summary": f"Deployment success ~{rate:.0%} ({completed}/{max(1, started)} started)",
    }


def build_brain_routing_confidence(truth: dict[str, Any]) -> dict[str, Any]:
    panel = truth.get("brain_routing_panel") or {}
    br = panel.get("brain_routing") or {}
    recent = panel.get("recent_decisions") or []
    fallback_rate = sum(1 for r in recent if r.get("fallback_used")) / max(1, len(recent))
    conf = br.get("routing_confidence") or br.get("capability_score")
    score = float(conf) if isinstance(conf, (int, float)) else 0.75
    if truth.get("routing_summary", {}).get("privacy_block_active"):
        score = min(score, 0.5)
    return {
        "routing_confidence": round(score, 3),
        "fallback_frequency": round(fallback_rate, 3),
        "local_first": br.get("local_first"),
        "local_only": br.get("local_only"),
        "privacy_mode": br.get("privacy_mode"),
        "selected_provider": br.get("selected_provider"),
        "estimated_cost": br.get("estimated_cost"),
        "summary": (
            f"Routing via {br.get('selected_provider') or 'default'} "
            f"({'fallback used' if br.get('fallback_used') else 'primary path'})"
        ),
    }


def build_marketplace_operational_stability(truth: dict[str, Any]) -> dict[str, Any]:
    plugins = truth.get("plugins") or {}
    packs = truth.get("automation_packs") or []
    mp = truth.get("marketplace") or {}
    pack_list = packs if isinstance(packs, list) else (packs.get("packs") if isinstance(packs, dict) else [])
    failed = int(plugins.get("failed_count") or 0)
    healthy = int(plugins.get("healthy_count") or 0)
    return {
        "plugin_healthy": healthy,
        "plugin_failed": failed,
        "installed_plugins": mp.get("installed_count") if isinstance(mp, dict) else healthy,
        "automation_packs": len(pack_list),
        "trust": "high" if failed == 0 else "degraded" if failed < 3 else "low",
        "summary": f"{healthy} healthy plugin(s)" + (f", {failed} failed" if failed else ""),
    }


def build_runtime_cost_visibility(truth: dict[str, Any]) -> dict[str, Any]:
    panel = truth.get("brain_routing_panel") or {}
    br = panel.get("brain_routing") or {}
    recent = panel.get("recent_decisions") or []
    est = sum(float(r.get("cost_estimate") or 0) for r in recent if isinstance(r.get("cost_estimate"), (int, float)))
    agent_m = (truth.get("runtime_metrics") or {}).get("agent_metrics") or {}
    return {
        "estimated_brain_cost_recent": round(est, 4) if est else br.get("estimated_cost"),
        "token_usage_estimate": (truth.get("runtime_metrics") or {}).get("token_usage_estimate"),
        "agent_actions_today": agent_m.get("total_actions_today"),
        "note": "Lightweight operational estimates — not billing.",
    }


def build_operator_onboarding_visibility(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    op = truth.get("operator_context") or {}
    inv = op.get("provider_inventory") or {}
    configured = 0
    if isinstance(inv, dict):
        for row in inv.values():
            if isinstance(row, dict) and (row.get("configured") or row.get("available")):
                configured += 1
    projects = op.get("project_registry") or {}
    proj_n = len((projects.get("projects") or {}) if isinstance(projects, dict) else {})
    plugins = int((truth.get("plugins") or {}).get("healthy_count") or 0)
    health = (truth.get("runtime_health") or {}).get("status") or "healthy"
    checks = [
        {"id": "runtime", "label": "Runtime healthy", "ok": health in ("healthy", "warning", "recovering")},
        {"id": "providers", "label": "Providers connected", "ok": configured > 0},
        {"id": "workspace", "label": "Workspace detected", "ok": bool(op.get("workspace_root") or (op.get("workspace") or {}).get("root"))},
        {"id": "projects", "label": "Projects linked", "ok": proj_n > 0},
        {"id": "plugins", "label": "Plugins optional", "ok": True},
    ]
    ready = sum(1 for c in checks if c["ok"])
    return {
        "readiness_score": round(ready / len(checks), 2),
        "checks": checks,
        "connected_providers": configured,
        "project_count": proj_n,
        "installed_plugins": plugins,
        "summary": f"{ready}/{len(checks)} onboarding checks passed",
    }


def _scalability_from_discipline(discipline: dict[str, Any]) -> dict[str, Any]:
    return {
        "truth_build_ms": discipline.get("last_truth_build_ms"),
        "payload_bytes": discipline.get("last_payload_approx_bytes"),
        "cache_hit_rate": discipline.get("truth_cache_hit_rate"),
        "event_buffer_size": discipline.get("event_buffer_size"),
        "office_payload_bytes": discipline.get("last_office_payload_bytes"),
    }
