# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final release candidate certification document bundle (Phase 4 Step 14)."""

from __future__ import annotations

from typing import Any

PASSED = [
    "tests/test_phase4_step14_runtime_evolution.py",
    "tests/test_release_candidate_certification.py",
    "tests/test_enterprise_stability_certification.py",
    "tests/test_runtime_pressure_behavior.py",
    "tests/test_enterprise_explainability.py",
    "tests/test_identity_convergence_final.py",
    "tests/test_runtime_release_candidate.py",
    "tests/test_operational_freeze_lock.py",
    "tests/test_office_launch_quality.py",
]

DEFERRED = [
    "tests/test_phase4_runtime_evolution_truth.py (full cold hydration)",
    "tests/test_openclaw_* (full matrix — CI/nightly)",
    "tests/e2e/runtime_surfaces/ (cold hydration — may hang locally)",
]


def build_final_release_candidate_certification() -> dict[str, Any]:
    return {
        "final_release_candidate_certification": {
            "release_candidate": True,
            "certified_phase": "phase4_step14",
            "passed_suites": PASSED,
            "deferred_suites": DEFERRED,
            "known_limitations": [
                "Cold hydration can take minutes on first process start",
                "E2E MC APIs may timeout without warm cache",
            ],
            "hydration_warnings": ["Use summary-first Office during warm-up", "Stale cache ≠ failure"],
            "scaling_guidance": "Single-tenant enterprise operator; raise event buffer only when needed",
            "deployment_posture": "orchestrator-first, advisory-first, bounded persistence",
            "runtime_expectations": "partial availability with calm degraded copy",
            "operational_guarantees": [
                "Orchestrator authority",
                "No hidden autonomy",
                "Explainability without log diving",
            ],
        }
    }
