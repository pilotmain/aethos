# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final enterprise runtime operational integrity certification (Phase 4 Step 25)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority
from app.services.runtime.runtime_recovery_authority import build_runtime_recovery_authority
from app.services.runtime.runtime_truth_ownership_lock import build_runtime_truth_authority

INTEGRITY_CATEGORIES = (
    "runtime_ownership",
    "process_integrity",
    "database_integrity",
    "startup_integrity",
    "hydration_integrity",
    "runtime_supervision",
    "runtime_recovery",
    "runtime_truth_authority",
    "runtime_responsiveness",
    "runtime_continuity",
    "operator_confidence",
)


def build_enterprise_runtime_integrity_final(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    ownership = build_runtime_ownership_authority(truth)
    recovery = build_runtime_recovery_authority(truth)
    truth_auth = build_runtime_truth_authority(truth)
    own_auth = ownership.get("runtime_ownership_authority") or {}
    proc_int = ownership.get("runtime_process_integrity") or {}
    db_int = ownership.get("database_runtime_integrity") or {}
    rec_auth = recovery.get("runtime_recovery_authority") or {}
    truth_a = truth_auth.get("runtime_truth_authority") or {}

    scores: dict[str, float] = {
        "runtime_ownership": 1.0 if own_auth.get("authoritative") else 0.6,
        "process_integrity": 1.0 if proc_int.get("integrity_ok") else 0.55,
        "database_integrity": 1.0 if db_int.get("ok") else 0.5,
        "startup_integrity": float((truth.get("runtime_startup_integrity") or {}).get("score") or 0.85),
        "hydration_integrity": 1.0 if truth_a.get("duplicate_hydration_prevented") else 0.6,
        "runtime_supervision": 1.0 if truth.get("runtime_supervision_verified") else 0.8,
        "runtime_recovery": 1.0 if rec_auth.get("authoritative") else 0.7,
        "runtime_truth_authority": 1.0 if truth_a.get("runtime_truth_authoritative") else 0.65,
        "runtime_responsiveness": float((truth.get("runtime_responsiveness_guarantees") or {}).get("score") or 0.85),
        "runtime_continuity": float((truth.get("runtime_operator_continuity_confidence") or {}).get("score") or 0.85),
        "operator_confidence": float((truth.get("operator_confidence") or {}).get("score") or 0.85),
    }
    overall = round(sum(scores.values()) / max(1, len(scores)), 3)
    verified = overall >= 0.85 and own_auth.get("single_owner_enforced")
    return {
        "enterprise_runtime_integrity_final": {
            "phase": "phase4_step25",
            "categories": {k: scores[k] for k in INTEGRITY_CATEGORIES},
            "integrity_score": overall,
            "enterprise_runtime_integrity_verified": verified,
            "runtime_coordination_authoritative": bool(own_auth.get("authoritative")),
            "runtime_recovery_certified": bool(rec_auth.get("authoritative")),
            "process_supervision_verified": bool(truth.get("runtime_supervision_verified")),
            "production_runtime_locked": verified and bool(truth.get("launch_stabilized")),
            "bounded": True,
        },
        "enterprise_runtime_integrity_verified": verified,
        "runtime_coordination_authoritative": bool(own_auth.get("authoritative")),
        "runtime_recovery_certified": bool(rec_auth.get("authoritative")),
        "process_supervision_verified": bool(truth.get("runtime_supervision_verified")),
        "production_runtime_locked": verified and bool(truth.get("launch_stabilized")),
    }
