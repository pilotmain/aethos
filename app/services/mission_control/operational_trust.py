# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational trust model and accountability (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.automation_governance import build_automation_trust
from app.services.mission_control.provider_governance_visibility import build_provider_trust
from app.services.mission_control.worker_accountability import build_worker_trust


def _clamp_score(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 3)


def build_governance_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    gov = (truth or {}).get("runtime_governance") or {}
    summary = gov.get("summary") if isinstance(gov, dict) else {}
    st = load_runtime_state()
    plugin_n = len(st.get("plugin_governance_audit") or []) if isinstance(st.get("plugin_governance_audit"), list) else 0
    prov_n = int(summary.get("provider_actions") or 0) if isinstance(summary, dict) else 0
    return {
        "audit_entries": plugin_n + prov_n,
        "privacy_events": int(summary.get("privacy_events") or 0) if isinstance(summary, dict) else 0,
        "integrity": "stable" if plugin_n < 200 else "review",
        "unified_timeline": True,
    }


def build_runtime_accountability(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    disc = (truth or {}).get("runtime_discipline") or {}
    perf = (truth or {}).get("runtime_performance") or {}
    return {
        "truth_cache_hit_rate": disc.get("truth_cache_hit_rate"),
        "last_hydration_ms": perf.get("hydration_latency_ms"),
        "payload_within_budget": ((truth or {}).get("payload_discipline") or {}).get("within_budget"),
        "orchestrator_owned": True,
        "no_hidden_execution": True,
    }


def build_operational_trust_score(truth: dict[str, Any] | None = None) -> float:
    health = (truth or {}).get("enterprise_operational_health") or {}
    overall = str(health.get("overall") or health.get("status") or "healthy").lower()
    base = {"healthy": 0.92, "warning": 0.72, "degraded": 0.55, "critical": 0.35}.get(overall, 0.75)
    prov = build_provider_trust(truth).get("score", 0.8)
    wrk = build_worker_trust(truth).get("score", 0.8)
    auto = build_automation_trust(truth).get("score", 0.85)
    return _clamp_score((base + float(prov) + float(wrk) + float(auto)) / 4.0)


def build_operational_trust_model(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "operational_trust_score": build_operational_trust_score(truth),
        "governance_integrity": build_governance_integrity(truth),
        "runtime_accountability": build_runtime_accountability(truth),
        "provider_trust": build_provider_trust(truth),
        "automation_trust": build_automation_trust(truth),
        "worker_trust": build_worker_trust(truth),
    }
