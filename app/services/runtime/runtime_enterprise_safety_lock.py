# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Production runtime safety lock — prevent duplicate coordination (Phase 4 Step 26)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_truth_ownership_lock import build_runtime_truth_authority


def build_runtime_enterprise_safety_lock(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    truth_auth = build_runtime_truth_authority(truth).get("runtime_truth_authority") or {}
    startup = truth.get("runtime_startup_integrity") or {}
    duplicate_prevented = bool(truth_auth.get("duplicate_hydration_prevented"))
    safe = duplicate_prevented and bool(startup.get("parallel_hydration_prevented", True))
    return {
        "runtime_enterprise_safety_lock": {
            "phase": "phase4_step26",
            "enterprise_runtime_safe": safe,
            "duplicate_runtime_activity_prevented": duplicate_prevented,
            "runtime_governance_locked": safe,
            "prevents": [
                "duplicate_truth_builders",
                "duplicate_startup_cycles",
                "duplicate_recovery_loops",
                "duplicate_runtime_coordination",
                "duplicate_governance_aggregators",
                "duplicate_hydration_ownership",
            ],
            "bounded": True,
        },
        "enterprise_runtime_safe": safe,
        "duplicate_runtime_activity_prevented": duplicate_prevented,
        "runtime_governance_locked": safe,
    }
