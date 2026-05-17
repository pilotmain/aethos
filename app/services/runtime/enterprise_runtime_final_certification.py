# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""FINAL enterprise runtime operational certification (Phase 4 Step 26)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority
from app.services.runtime.runtime_enterprise_safety_lock import build_runtime_enterprise_safety_lock
from app.services.runtime.runtime_trust_finalization import build_runtime_trust_finalization
from app.services.runtime.runtime_truth_governance_lock import build_runtime_truth_governance_lock

CERTIFICATION_CATEGORIES = (
    "runtime_governance",
    "runtime_integrity",
    "runtime_ownership",
    "runtime_recovery",
    "runtime_supervision",
    "runtime_startup",
    "runtime_truth_authority",
    "runtime_operational_stability",
    "runtime_continuity",
    "runtime_responsiveness",
    "runtime_trust",
    "runtime_explainability",
    "runtime_calmness",
    "runtime_operator_experience",
    "runtime_enterprise_readiness",
)


def build_enterprise_runtime_final_certification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    gov = build_runtime_governance_authority(truth)
    safety = build_runtime_enterprise_safety_lock(truth)
    trust = build_runtime_trust_finalization(truth)
    truth_lock = build_runtime_truth_governance_lock(truth)
    blockers: list[str] = []
    scores: dict[str, bool] = {
        "runtime_governance": bool((gov.get("runtime_governance_authority") or {}).get("authoritative")),
        "runtime_integrity": bool(truth.get("enterprise_runtime_integrity_verified")),
        "runtime_ownership": bool(truth.get("runtime_ownership_authoritative")),
        "runtime_recovery": bool(truth.get("runtime_recovery_certified")),
        "runtime_supervision": bool(truth.get("runtime_supervision_verified")),
        "runtime_startup": bool((truth.get("runtime_startup_integrity") or {}).get("score", 0) >= 0.65),
        "runtime_truth_authority": bool(truth_lock.get("runtime_truth_authority_finalized")),
        "runtime_operational_stability": bool(truth.get("launch_stabilized")),
        "runtime_continuity": bool((truth.get("runtime_operator_continuity_confidence") or {}).get("score", 0) >= 0.7),
        "runtime_responsiveness": bool((truth.get("runtime_responsiveness_guarantees") or {}).get("score", 0) >= 0.7),
        "runtime_trust": bool(trust.get("enterprise_runtime_trusted")),
        "runtime_explainability": bool((gov.get("runtime_governance_visibility") or {}).get("explainable")),
        "runtime_calmness": bool((truth.get("runtime_calmness_lock") or {}).get("locked")),
        "runtime_operator_experience": bool(truth.get("runtime_operator_experience")),
        "runtime_enterprise_readiness": bool(truth.get("production_cut_certified")),
    }
    for k, ok in scores.items():
        if not ok:
            blockers.append(k)
    certified = len(blockers) == 0
    return {
        "enterprise_runtime_final_certification": {
            "phase": "phase4_step26",
            "categories": scores,
            "enterprise_runtime_fully_certified": certified,
            "enterprise_runtime_governed": bool(gov.get("enterprise_runtime_governance", {}).get("governed")),
            "enterprise_runtime_stabilized": bool(safety.get("enterprise_runtime_safe")),
            "enterprise_runtime_trusted": bool(trust.get("enterprise_runtime_trusted")),
            "production_runtime_finalized": certified and bool(truth.get("production_runtime_locked")),
            "remaining_blockers": blockers[:12],
            "bounded": True,
        },
        "enterprise_runtime_fully_certified": certified,
        "enterprise_runtime_governed": bool(gov.get("enterprise_runtime_governance", {}).get("governed")),
        "enterprise_runtime_stabilized": bool(safety.get("enterprise_runtime_safe")),
        "production_runtime_finalized": certified and bool(truth.get("production_runtime_locked")),
    }
