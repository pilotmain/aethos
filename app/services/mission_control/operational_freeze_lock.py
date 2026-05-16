# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Launch candidate operational freeze lock (Phase 4 Step 14)."""

from __future__ import annotations

from typing import Any

FROZEN_SURFACES = (
    "build_runtime_truth",
    "apply_runtime_evolution",
    "mission_control/office",
    "setup/onboarding",
    "runtime_capabilities registry",
)

FROZEN_APIS = (
    "/api/v1/mission-control/office",
    "/api/v1/runtime/capabilities",
    "/api/v1/setup/certify",
    "/api/v1/runtime/release-candidate",
)


def build_operational_freeze_lock() -> dict[str, Any]:
    return {
        "operational_freeze_lock": {
            "release_candidate": True,
            "frozen_runtime_surfaces": list(FROZEN_SURFACES),
            "frozen_truth_architecture": "build_runtime_truth → evolution steps 1–14",
            "frozen_mission_control_apis": True,
            "frozen_onboarding_flow": True,
            "frozen_setup_contract": True,
            "frozen_office_model": "command-center summary-first",
            "breaking_changes_disallowed": True,
            "bounded": True,
        },
        "production_surface_lock": {
            "additive_only": True,
            "experimental_surfaces_frozen": True,
            "api_paths_locked": list(FROZEN_APIS),
        },
    }
