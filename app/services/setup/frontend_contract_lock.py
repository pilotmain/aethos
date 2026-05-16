# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Frontend/backend route contract lock (Phase 4 Step 11)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_api_capabilities import build_runtime_capabilities

# Mission Control fetch paths that must exist on the API registry (or MC router).
FRONTEND_RUNTIME_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/runtime/capabilities",
        "/api/v1/runtime/summaries",
        "/api/v1/runtime/hydration",
        "/api/v1/mission-control/office",
        "/api/v1/mission-control/state",
        "/api/v1/mission-control/onboarding",
        "/api/v1/mission-control/runtime/overview",
        "/api/v1/mission-control/governance-experience",
        "/api/v1/mission-control/executive-overview",
        "/api/v1/setup/status",
    }
)


def build_frontend_backend_contract_lock() -> dict[str, Any]:
    caps = build_runtime_capabilities()
    registered = {r.get("path") for r in caps.get("available_routes") or [] if r.get("path")}
    missing = sorted(p for p in FRONTEND_RUNTIME_PATHS if p not in registered)
    mc_prefix_ok = any("/mission-control/" in p for p in registered)
    return {
        "locked": len(missing) == 0 or mc_prefix_ok,
        "capabilities_version": caps.get("mc_compatibility_version"),
        "frontend_paths": sorted(FRONTEND_RUNTIME_PATHS),
        "missing_from_capabilities_registry": missing,
        "registered_count": len(registered),
        "error_semantics": {
            "404": "Feature unavailable",
            "500": "Runtime service error",
            "offline": "API offline — check Connection settings",
        },
    }
