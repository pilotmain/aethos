# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deprecated runtime keys, routes, and views (Phase 4 Step 20)."""

from __future__ import annotations

from typing import Any

DEPRECATED_RUNTIME_KEYS: dict[str, str] = {
    "runtime_cohesion_summary": "Use runtime_cohesion",
    "mission_control_summary": "Removed — use mission-control/state",
}

DEPRECATED_ROUTES: dict[str, str] = {
    "/api/v1/mission-control/summary": "/api/v1/mission-control/state",
}

DEPRECATED_VIEWS: dict[str, str] = {
    "/mission-control/ceo": "/mission-control/office",
    "/mission-control/overview": "/mission-control/runtime-overview",
}


def build_runtime_deprecation_registry() -> dict[str, Any]:
    return {
        "runtime_deprecation_registry": {
            "deprecated_runtime_keys": DEPRECATED_RUNTIME_KEYS,
            "deprecated_routes": DEPRECATED_ROUTES,
            "deprecated_views": DEPRECATED_VIEWS,
            "removal_policy": "compat_aliases_retained_until_phase5",
            "bounded": True,
        }
    }
