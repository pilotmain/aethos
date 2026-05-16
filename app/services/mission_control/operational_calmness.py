# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational calmness and quality metrics (Phase 3 Step 15)."""

from __future__ import annotations

from typing import Any


def build_runtime_calmness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = truth.get("operational_pressure") or {}
    esc_n = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    crit = len((truth.get("office") or {}).get("critical_events") or []) if isinstance(truth.get("office"), dict) else 0
    rec_n = len(((truth.get("runtime_recommendations") or {}).get("recommendations") or []))
    level = str(pressure.get("level") or "low")
    calm_score = 1.0
    if level == "high":
        calm_score -= 0.35
    elif level == "medium":
        calm_score -= 0.15
    calm_score -= min(0.3, esc_n * 0.05)
    calm_score -= min(0.2, crit * 0.08)
    calm_score -= min(0.15, max(0, rec_n - 6) * 0.02)
    calm_score = round(max(0.0, min(1.0, calm_score)), 3)
    return {
        "calm_score": calm_score,
        "pressure_level": level,
        "escalation_count": esc_n,
        "critical_events": crit,
        "recommendation_count": rec_n,
        "feels_calm": calm_score >= 0.7,
        "prioritized_events": _prioritized_events(truth),
    }


def build_operational_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    calm = build_runtime_calmness(truth)
    trust = float(truth.get("operational_trust_score") or 0.75)
    clarity = 0.9 if truth.get("operational_explainability") else 0.6
    gov_vis = 0.85 if (truth.get("unified_operational_timeline") or {}).get("authoritative") else 0.5
    score = round((calm.get("calm_score", 0.7) + trust + clarity + gov_vis) / 4.0, 3)
    return {
        "quality_score": score,
        "operational_clarity": round(clarity, 3),
        "governance_visibility_quality": round(gov_vis, 3),
        "recommendation_usefulness": _rec_usefulness(truth),
        "worker_effectiveness": ((truth.get("worker_accountability") or {}).get("reliability")),
        "provider_reliability": ((truth.get("provider_trust") or {}).get("score")),
        "automation_usefulness": ((truth.get("automation_trust") or {}).get("score")),
    }


def _prioritized_events(truth: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for esc in ((truth.get("runtime_escalations") or {}).get("active_escalations") or [])[:4]:
        if isinstance(esc, dict):
            out.append({"priority": "high", "type": esc.get("type"), "severity": esc.get("severity")})
    for e in (truth.get("runtime_events") or [])[:4]:
        if isinstance(e, dict) and str(e.get("severity") or "") in ("critical", "error"):
            out.append({"priority": "medium", "event_type": e.get("event_type")})
    return out[:8]


def _rec_usefulness(truth: dict[str, Any]) -> float:
    recs = ((truth.get("runtime_recommendations") or {}).get("recommendations") or [])
    if not recs:
        return 0.85
    with_reason = sum(1 for r in recs if isinstance(r, dict) and r.get("reason"))
    return round(with_reason / max(1, len(recs)), 3)
