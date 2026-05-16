# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime API capability registry for MC/CLI discovery (Phase 4 Step 6)."""

from __future__ import annotations

from typing import Any

MC_COMPATIBILITY_VERSION = "phase4_step16"

_AVAILABLE_ROUTES: list[dict[str, str]] = [
    {"method": "GET", "path": "/api/v1/mission-control/state"},
    {"method": "GET", "path": "/api/v1/mission-control/office"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/intelligence"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/posture"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/recovery"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/routing"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/continuity"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/advisories"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/focus"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime-recovery"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/integrity"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime/lazy/{view}"},
    {"method": "GET", "path": "/api/v1/providers/usage"},
    {"method": "GET", "path": "/api/v1/runtime/capabilities"},
    {"method": "GET", "path": "/api/v1/runtime/performance"},
    {"method": "GET", "path": "/api/v1/runtime/hydration"},
    {"method": "GET", "path": "/api/v1/runtime/payloads"},
    {"method": "GET", "path": "/api/v1/runtime/throttling"},
    {"method": "GET", "path": "/api/v1/runtime/responsiveness"},
    {"method": "GET", "path": "/api/v1/runtime/profile/{profile}"},
    {"method": "GET", "path": "/api/v1/mission-control/workers/archive"},
    {"method": "GET", "path": "/api/v1/runtime/partitions"},
    {"method": "GET", "path": "/api/v1/runtime/eras"},
    {"method": "GET", "path": "/api/v1/runtime/production-posture"},
    {"method": "GET", "path": "/api/v1/runtime/summaries"},
    {"method": "GET", "path": "/api/v1/runtime/calmness-lock"},
    {"method": "GET", "path": "/api/v1/mission-control/governance/index"},
    {"method": "GET", "path": "/api/v1/mission-control/workers/lifecycle"},
    {"method": "GET", "path": "/api/v1/mission-control/governance-experience"},
    {"method": "GET", "path": "/api/v1/mission-control/executive-overview"},
    {"method": "GET", "path": "/api/v1/mission-control/runtime-story"},
    {"method": "GET", "path": "/api/v1/mission-control/explainability"},
    {"method": "GET", "path": "/api/v1/mission-control/timeline-experience"},
    {"method": "GET", "path": "/api/v1/mission-control/onboarding"},
    {"method": "GET", "path": "/api/v1/setup/status"},
    {"method": "GET", "path": "/api/v1/runtime/routing"},
    {"method": "GET", "path": "/api/v1/runtime/restarts"},
    {"method": "GET", "path": "/api/v1/runtime/identity"},
    {"method": "GET", "path": "/api/v1/setup/ready-state"},
    {"method": "GET", "path": "/api/v1/setup/certify"},
    {"method": "GET", "path": "/api/v1/setup/env-audit"},
    {"method": "GET", "path": "/api/v1/setup/one-curl"},
    {"method": "GET", "path": "/api/v1/setup/continuity"},
    {"method": "GET", "path": "/api/v1/setup/operator-profile"},
    {"method": "GET", "path": "/api/v1/setup/experience"},
    {"method": "GET", "path": "/api/v1/setup/first-impression"},
    {"method": "GET", "path": "/api/v1/setup/doctor"},
    {"method": "GET", "path": "/api/v1/runtime/routing/history"},
    {"method": "GET", "path": "/api/v1/runtime/routing/explanations"},
    {"method": "GET", "path": "/api/v1/runtime/providers/health-matrix"},
    {"method": "GET", "path": "/api/v1/runtime/perception"},
    {"method": "GET", "path": "/api/v1/runtime/operator-experience"},
    {"method": "GET", "path": "/api/v1/runtime/operational-focus"},
    {"method": "GET", "path": "/api/v1/runtime/priority-work"},
    {"method": "GET", "path": "/api/v1/runtime/noise-reduction"},
    {"method": "GET", "path": "/api/v1/runtime/calmness-metrics"},
    {"method": "GET", "path": "/api/v1/runtime/signal-health"},
    {"method": "GET", "path": "/api/v1/runtime/launch-certification"},
    {"method": "GET", "path": "/api/v1/runtime/readiness-progress"},
    {"method": "GET", "path": "/api/v1/runtime/cold-start"},
    {"method": "GET", "path": "/api/v1/runtime/partial-availability"},
    {"method": "GET", "path": "/api/v1/runtime/release-candidate"},
    {"method": "GET", "path": "/api/v1/runtime/certification"},
    {"method": "GET", "path": "/api/v1/runtime/enterprise-grade"},
    {"method": "GET", "path": "/api/v1/runtime/startup"},
    {"method": "GET", "path": "/api/v1/runtime/readiness"},
    {"method": "GET", "path": "/api/v1/runtime/hydration/stages"},
    {"method": "GET", "path": "/api/v1/runtime/compatibility"},
    {"method": "GET", "path": "/api/v1/runtime/bootstrap"},
    {"method": "GET", "path": "/api/v1/runtime/branding-audit"},
    {"method": "GET", "path": "/api/v1/health"},
]

_DEPRECATED_ROUTES: list[dict[str, str]] = [
    {"method": "GET", "path": "/api/v1/mission-control/summary", "replacement": "/api/v1/mission-control/state"},
]

_DISABLED_ROUTES: list[dict[str, str]] = []


def build_runtime_capabilities() -> dict[str, Any]:
    return {
        "mc_compatibility_version": MC_COMPATIBILITY_VERSION,
        "available_routes": list(_AVAILABLE_ROUTES),
        "disabled_routes": list(_DISABLED_ROUTES),
        "deprecated_routes": list(_DEPRECATED_ROUTES),
        "feature_flags": {
            "runtime_resilience": True,
            "lazy_views": True,
            "truth_integrity": True,
            "recovery_center": True,
            "degraded_mode": True,
            "phase4_step6": True,
            "phase4_step7": True,
            "phase4_step8": True,
            "progressive_hydration": True,
            "payload_profiles": True,
            "production_convergence": True,
            "phase4_step9": True,
            "operational_surfaces": True,
            "phase4_step10": True,
            "phase4_step11": True,
            "enterprise_setup": True,
            "ready_state_lock": True,
            "phase4_step12": True,
            "production_cut": True,
            "phase4_step13": True,
            "launch_ready": True,
            "phase4_step14": True,
            "release_candidate": True,
            "phase4_step15": True,
            "conversational_installer": True,
            "phase4_step16": True,
            "enterprise_setup_finalized": True,
        },
        "lazy_views": [
            "routing",
            "posture",
            "continuity",
            "advisories",
            "strategy",
            "recovery",
            "governance",
        ],
    }


def route_available(method: str, path: str) -> bool:
    m = method.upper()
    for r in _AVAILABLE_ROUTES:
        if r.get("method", "").upper() == m and r.get("path") == path:
            return True
    return False
