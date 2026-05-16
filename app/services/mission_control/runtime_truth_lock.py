# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime truth authority lock and discipline validation (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any

AUTHORITATIVE_BUILDER = "hydrate_runtime_truth_incremental"
CANONICAL_ENTRY = "build_runtime_truth"


def validate_truth_discipline(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    warnings: list[str] = []
    required_keys = (
        "runtime_identity",
        "enterprise_operational_health",
        "unified_operational_timeline",
        "operational_trust_score",
        "runtime_cohesion",
        "payload_discipline",
    )
    missing = [k for k in required_keys if k not in truth]
    if missing:
        warnings.append(f"truth_missing_keys:{','.join(missing)}")
    if not (truth.get("unified_operational_timeline") or {}).get("authoritative"):
        warnings.append("timeline_not_authoritative")
    if truth.get("_ort"):
        warnings.append("internal_slice_leaked:_ort")
    duplicate_timeline = bool(truth.get("unified_operational_timeline")) and not truth.get("runtime_identity")
    if duplicate_timeline:
        warnings.append("fragmented_identity")
    return {
        "authoritative_builder": AUTHORITATIVE_BUILDER,
        "canonical_entry": CANONICAL_ENTRY,
        "single_truth_path": len(missing) == 0,
        "warnings": warnings,
        "duplicate_builder_detected": False,
        "disconnected_surfaces": missing,
        "stale_api_risk": len(warnings) > 0,
        "truth_fragmentation": len(missing) > 2,
        "locked": len(warnings) == 0,
    }


def build_truth_lock_status(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = validate_truth_discipline(truth)
    return {
        **validation,
        "truth_authority": "runtime",
        "orchestrator_owned": True,
        "cache_slices_enabled": True,
        "message": "Runtime truth locked — all MC surfaces must use get_cached_runtime_truth"
        if validation.get("locked")
        else "Truth discipline warnings present — review hydration path",
    }
