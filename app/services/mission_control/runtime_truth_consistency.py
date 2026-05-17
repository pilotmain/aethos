# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime truth consistency and integrity scoring (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_truth_schema_lock import (
    DUPLICATE_SEMANTIC_PAIRS,
    validate_runtime_truth_schema,
)


def build_runtime_truth_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    schema = validate_runtime_truth_schema(truth)["runtime_truth_schema_lock"]
    stale = (truth.get("runtime_resilience") or {}).get("status") in ("stale", "partial")
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    warnings = list(schema.get("warnings") or [])
    if stale:
        warnings.append("stale_truth_detected")
    if partial:
        warnings.append("partial_hydration_active")
    duplicate_keys = [a for a, b in DUPLICATE_SEMANTIC_PAIRS if a in truth and b in truth]
    score = 1.0
    score -= 0.1 * len(duplicate_keys)
    score -= 0.15 if stale else 0
    score -= 0.1 if partial else 0
    score -= 0.05 * len(schema.get("missing_required") or [])
    score = max(0.0, min(1.0, round(score, 3)))
    return {
        "runtime_truth_integrity": {
            "truth_consistency_score": score,
            "duplicate_keys": duplicate_keys,
            "stale_truth": stale,
            "partial_truth": partial,
            "schema_valid": schema.get("valid"),
            "warnings": warnings,
            "phase": "phase4_step22",
            "bounded": True,
        }
    }


def build_runtime_truth_consistency(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    integrity = build_runtime_truth_integrity(truth)["runtime_truth_integrity"]
    return {
        "runtime_truth_consistency": {
            **integrity,
            "consistent": integrity.get("truth_consistency_score", 0) >= 0.8 and integrity.get("schema_valid"),
            "bounded": True,
        }
    }
