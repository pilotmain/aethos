# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime duplication lock — single truth authority map (Phase 4 Step 13)."""

from __future__ import annotations

from typing import Any

AUTHORITATIVE_PATH = "build_runtime_truth() → get_cached_runtime_truth()"

DERIVED_SURFACES = (
    "runtime_operator_experience",
    "runtime_enterprise_summarization",
    "enterprise_operator_experience",
    "runtime_cohesion",
    "office",
    "runtime_recovery_center",
)

COMPATIBILITY_ONLY = (
    "legacy mission_control_runtime builders (slice APIs)",
    "nexa_next_state snapshot embed",
)


def build_runtime_duplication_lock(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "runtime_duplication_lock": {
            "authoritative": AUTHORITATIVE_PATH,
            "derived_surfaces": list(DERIVED_SURFACES),
            "compatibility_only": list(COMPATIBILITY_ONLY),
            "single_truth_authority": True,
            "orchestrator_owned": True,
        },
        "truth_ownership_map": {
            "primary": AUTHORITATIVE_PATH,
            "hydration": "hydrate_runtime_truth_incremental()",
            "evolution": "apply_runtime_evolution_to_truth()",
        },
        "intentional_duplicates_documented": True,
        "bounded": True,
    }
