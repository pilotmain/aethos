# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 21 — operator-facing branding convergence and enterprise UX completion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.setup.final_branding_convergence_audit import build_final_branding_convergence_audit


def apply_runtime_evolution_step21_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    from app.services.mission_control.operator_language_system import build_operator_language_system
    from app.services.mission_control.provider_routing_ux import build_provider_routing_ux
    from app.services.mission_control.runtime_calmness_lock import build_runtime_calmness_lock
    from app.services.mission_control.runtime_narrative_unification import build_runtime_narrative_unification
    from app.services.mission_control.runtime_simplification_lock import build_runtime_simplification_lock

    truth.update(build_final_branding_convergence_audit(repo_root=Path.cwd()))
    truth.update(build_runtime_narrative_unification(truth))
    truth.update(build_runtime_simplification_lock(truth))
    truth.update(build_provider_routing_ux(truth))
    truth.update(build_runtime_calmness_lock(truth))
    truth.update(build_operator_language_system(truth))
    audit = truth.get("final_branding_convergence_audit") or {}
    truth["phase4_step21"] = True
    truth["operator_facing_branding_locked"] = bool(audit.get("near_zero_operator_goal"))
    truth["enterprise_ux_completed"] = True
    return truth
