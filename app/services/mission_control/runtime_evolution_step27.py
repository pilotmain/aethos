# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 27 — operational command finalization."""

from __future__ import annotations

from typing import Any


def apply_runtime_evolution_step27_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    from app.services.mission_control.office_operational_authority import build_office_operational_authority
    from app.services.runtime.enterprise_operational_command_authority import build_enterprise_operational_command_authority
    from app.services.runtime.enterprise_runtime_finalization_certification import (
        build_enterprise_runtime_finalization_certification,
    )
    from app.services.runtime.runtime_enterprise_confidence_engine import build_runtime_enterprise_confidence_engine
    from app.services.runtime.runtime_governance_consolidation import build_runtime_governance_consolidation
    from app.services.runtime.runtime_operational_stability_finalization import build_runtime_operational_stability_finalization
    from app.services.runtime.runtime_readiness_convergence import build_runtime_readiness_convergence
    from app.services.runtime.runtime_recovery_experience_finalization import build_runtime_recovery_experience_finalization
    from app.services.runtime.runtime_unified_narrative_engine import build_runtime_unified_narrative_engine
    from app.services.runtime.runtime_visibility_authority import build_runtime_visibility_authority

    truth.update(build_runtime_readiness_convergence(truth))
    truth.update(build_runtime_unified_narrative_engine(truth))
    truth.update(build_runtime_visibility_authority(truth))
    truth.update(build_enterprise_operational_command_authority(truth))
    truth.update(build_runtime_operational_stability_finalization(truth))
    truth.update(build_runtime_recovery_experience_finalization(truth))
    truth.update(build_runtime_governance_consolidation(truth))
    truth.update(build_runtime_enterprise_confidence_engine(truth))
    truth.update(build_office_operational_authority(truth))
    truth.update(build_enterprise_runtime_finalization_certification(truth))
    final = truth.get("enterprise_runtime_finalization_certification") or {}
    truth["phase4_step27"] = True
    truth["enterprise_runtime_finalized"] = bool(final.get("enterprise_runtime_finalized"))
    truth["enterprise_operational_command_locked"] = bool(final.get("enterprise_operational_command_locked"))
    truth["runtime_governance_converged"] = bool(final.get("runtime_governance_converged"))
    truth["runtime_operationally_authoritative"] = bool(final.get("runtime_operationally_authoritative"))
    truth["runtime_enterprise_grade_verified"] = bool(final.get("runtime_enterprise_grade_verified"))
    return truth
