# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Production-cut readiness report (Phase 4 Step 12)."""

from __future__ import annotations

from typing import Any

VERIFIED_SUITES = [
    "tests/test_one_curl_enterprise_path.py",
    "tests/test_runtime_restart_manager.py",
    "tests/test_phase4_step10_runtime_evolution.py",
    "tests/test_setup_ready_state_lock.py",
    "tests/e2e/setup/",
]

DEFERRED_SUITES = [
    "tests/test_phase4_runtime_evolution_truth.py (full cold hydration)",
    "tests/test_openclaw_* (full parity — run in CI)",
]

KNOWN_SLOW = [
    "build_runtime_truth() cold hydration",
    "first MC API hit after process start",
]


def build_production_cut_readiness() -> dict[str, Any]:
    return {
        "production_cut_ready": True,
        "verified_suites": VERIFIED_SUITES,
        "deferred_suites": DEFERRED_SUITES,
        "known_slow_paths": KNOWN_SLOW,
        "acceptable_degradation": ["stale truth cache during hydration", "partial Office stream"],
        "recommended_posture": "orchestrator-first, advisory-first, bounded persistence",
        "phase": "phase4_step13",
    }
