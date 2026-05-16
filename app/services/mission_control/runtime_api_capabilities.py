# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime API capability registry for MC/CLI discovery (Phase 4 Step 6)."""

from __future__ import annotations

from typing import Any

MC_COMPATIBILITY_VERSION = "phase4_step6"

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
