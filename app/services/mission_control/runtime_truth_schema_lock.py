# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime truth schema lock and contract (Phase 4 Step 20)."""

from __future__ import annotations

from typing import Any

RUNTIME_TRUTH_CONTRACT_VERSION = "aethos_runtime_truth_v1"

REQUIRED_TRUTH_KEYS = (
    "runtime_resilience",
    "runtime_readiness_score",
    "enterprise_overview",
    "hydration_progress",
    "runtime_process_supervision",
)

DUPLICATE_SEMANTIC_PAIRS = (
    ("runtime_cohesion", "runtime_cohesion_summary"),
    ("operational_recovery_state", "runtime_recovery_center"),
)

MAX_TRUTH_KEY_COUNT = 220
MAX_NESTED_LIST_ITEMS = 64


def validate_runtime_truth_schema(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    missing = [k for k in REQUIRED_TRUTH_KEYS if k not in truth]
    duplicates = [a for a, b in DUPLICATE_SEMANTIC_PAIRS if a in truth and b in truth]
    key_count = len(truth)
    oversized = key_count > MAX_TRUTH_KEY_COUNT
    warnings: list[str] = []
    if missing:
        warnings.append(f"missing_required:{','.join(missing)}")
    if duplicates:
        warnings.append(f"duplicate_semantics:{','.join(duplicates)}")
    if oversized:
        warnings.append("truth_key_count_high")
    phase_ok = bool(
        truth.get("phase4_step22")
        or truth.get("phase4_step21")
        or truth.get("phase4_step20")
        or truth.get("runtime_supervision_verified")
    )
    stale = (truth.get("runtime_resilience") or {}).get("status") in ("stale", "partial")
    if stale:
        warnings.append("stale_truth")
    if (truth.get("hydration_progress") or {}).get("partial"):
        warnings.append("partial_hydration")
    return {
        "runtime_truth_schema_lock": {
            "contract_version": RUNTIME_TRUTH_CONTRACT_VERSION,
            "valid": len(missing) == 0 and not oversized,
            "missing_required": missing,
            "duplicate_semantics": duplicates,
            "duplicate_key_detection": len(duplicates) > 0,
            "conflicting_semantics": duplicates,
            "stale_truth_detection": stale,
            "partial_truth_validation": not bool((truth.get("hydration_progress") or {}).get("partial")),
            "key_count": key_count,
            "phase_complete": phase_ok,
            "warnings": warnings,
            "bounded_payload": not oversized,
            "bounded": True,
        }
    }


def build_runtime_truth_schema_lock(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return validate_runtime_truth_schema(truth)
