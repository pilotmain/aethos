# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational payload profiles — profile-specific truth views (Phase 4 Step 7)."""

from __future__ import annotations

from typing import Any

PROFILES = frozenset({"minimal", "office", "operational", "enterprise", "full"})

_PROFILE_KEYS: dict[str, frozenset[str]] = {
    "minimal": frozenset(
        {
            "runtime_health",
            "runtime_resilience",
            "operational_status",
            "operational_pressure",
            "hydration_metrics",
            "runtime_performance",
        }
    ),
    "office": frozenset(
        {
            "office",
            "runtime_agents",
            "routing_summary",
            "runtime_health",
            "runtime_workers",
            "runtime_resilience",
            "operational_pressure",
            "runtime_confidence",
            "hydration_metrics",
            "office_operational_stream",
        }
    ),
    "operational": frozenset(
        {
            "intelligent_routing",
            "operational_recovery_state",
            "runtime_awareness",
            "operational_continuity_engine",
            "strategic_recommendations",
            "strategic_runtime_planning",
            "runtime_recovery_center",
            "runtime_performance_intelligence",
            "runtime_operational_throttling",
        }
    ),
    "enterprise": frozenset(
        {
            "enterprise_overview",
            "enterprise_operational_posture",
            "enterprise_readiness",
            "runtime_truth_integrity",
            "runtime_api_capabilities",
        }
    ),
}


def apply_payload_profile(truth: dict[str, Any], profile: str) -> dict[str, Any]:
    name = (profile or "full").strip().lower()
    if name not in PROFILES or name == "full":
        return dict(truth)
    keys = _PROFILE_KEYS.get(name, frozenset())
    base = {k: truth[k] for k in keys if k in truth}
    base["payload_profile"] = name
    base["profile_key_count"] = len(base)
    if name == "office" and "office" not in base and truth.get("office"):
        base["office"] = truth["office"]
    return base


def build_payload_profile_metrics(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    from app.services.mission_control.runtime_metrics_discipline import approx_payload_bytes

    full_bytes = approx_payload_bytes(truth)
    profiles = {}
    for p in ("minimal", "office", "operational", "enterprise"):
        profiles[p] = approx_payload_bytes(apply_payload_profile(truth, p))
    return {
        "profiles": profiles,
        "full_bytes": full_bytes,
        "compression_ratio": round(profiles.get("office", full_bytes) / max(1, full_bytes), 4),
    }
