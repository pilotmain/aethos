# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final operational convergence certification (Phase 4 Step 27)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.enterprise_operational_command_authority import build_enterprise_operational_command_authority
from app.services.runtime.runtime_enterprise_confidence_engine import build_runtime_enterprise_confidence_engine
from app.services.runtime.runtime_governance_consolidation import build_runtime_governance_consolidation
from app.services.runtime.runtime_operational_stability_finalization import build_runtime_operational_stability_finalization
from app.services.runtime.runtime_readiness_convergence import build_runtime_readiness_convergence
from app.services.runtime.runtime_unified_narrative_engine import build_runtime_unified_narrative_engine
from app.services.runtime.runtime_visibility_authority import build_runtime_visibility_authority

CERTIFICATION_CATEGORIES = (
    "runtime_governance",
    "runtime_visibility",
    "runtime_readiness",
    "runtime_recovery",
    "runtime_continuity",
    "runtime_supervision",
    "runtime_stability",
    "runtime_truth_authority",
    "runtime_operational_command",
    "runtime_trust",
    "runtime_operator_experience",
    "runtime_confidence",
    "runtime_explainability",
    "runtime_calmness",
    "runtime_enterprise_finalization",
)


def build_enterprise_runtime_finalization_certification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    cmd = build_enterprise_operational_command_authority(truth)
    vis = build_runtime_visibility_authority(truth)
    readiness = build_runtime_readiness_convergence(truth)
    stability = build_runtime_operational_stability_finalization(truth)
    gov = build_runtime_governance_consolidation(truth)
    confidence = build_runtime_enterprise_confidence_engine(truth)
    narrative = build_runtime_unified_narrative_engine(truth)
    blockers: list[str] = []
    scores: dict[str, bool] = {
        "runtime_governance": bool((gov.get("enterprise_runtime_governance_final") or {}).get("finalized")),
        "runtime_visibility": bool((vis.get("runtime_visibility_authority") or {}).get("authoritative")),
        "runtime_readiness": bool((readiness.get("runtime_readiness_convergence") or {}).get("canonical")),
        "runtime_recovery": bool(truth.get("runtime_recovery_certified")),
        "runtime_continuity": bool((truth.get("runtime_operator_continuity_confidence") or {}).get("score", 0) >= 0.7),
        "runtime_supervision": bool(truth.get("runtime_supervision_verified")),
        "runtime_stability": bool(stability.get("runtime_operationally_stable")),
        "runtime_truth_authority": bool(truth.get("runtime_truth_governed")),
        "runtime_operational_command": bool((cmd.get("enterprise_operational_command_authority") or {}).get("authoritative")),
        "runtime_trust": bool(truth.get("enterprise_runtime_trusted")),
        "runtime_operator_experience": bool(truth.get("runtime_operator_experience")),
        "runtime_confidence": bool(confidence.get("runtime_enterprise_confidence_verified")),
        "runtime_explainability": bool((vis.get("runtime_visibility_authority") or {}).get("explainable")),
        "runtime_calmness": bool((truth.get("runtime_calmness_lock") or {}).get("locked")),
        "runtime_enterprise_finalization": bool(truth.get("production_runtime_finalized")),
    }
    for k, ok in scores.items():
        if not ok:
            blockers.append(k)
    finalized = len(blockers) == 0
    return {
        "enterprise_runtime_finalization_certification": {
            "phase": "phase4_step27",
            "categories": scores,
            "enterprise_runtime_finalized": finalized,
            "enterprise_operational_command_locked": bool(
                (cmd.get("enterprise_operational_command_authority") or {}).get("authoritative")
            ),
            "runtime_governance_converged": bool((gov.get("runtime_governance_consolidation") or {}).get("converged")),
            "runtime_operationally_authoritative": bool((vis.get("runtime_visibility_authority") or {}).get("authoritative")),
            "runtime_enterprise_grade_verified": finalized,
            "unified_narrative": narrative.get("runtime_unified_narrative"),
            "remaining_blockers": blockers[:12],
            "bounded": True,
        },
        "enterprise_runtime_finalized": finalized,
        "enterprise_operational_command_locked": bool(
            (cmd.get("enterprise_operational_command_authority") or {}).get("authoritative")
        ),
        "runtime_governance_converged": bool((gov.get("runtime_governance_consolidation") or {}).get("converged")),
        "runtime_operationally_authoritative": bool((vis.get("runtime_visibility_authority") or {}).get("authoritative")),
        "runtime_enterprise_grade_verified": finalized,
    }
