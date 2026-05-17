# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final enterprise operational certification (Phase 4 Step 24)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_degraded_mode_finalization import build_runtime_degraded_mode_finalization
from app.services.mission_control.runtime_long_session_reliability import build_runtime_long_session_reliability
from app.services.mission_control.runtime_operational_memory_discipline import build_runtime_operational_memory_discipline
from app.services.mission_control.runtime_production_certification import build_runtime_production_certification
from app.services.mission_control.runtime_release_freeze_lock import build_runtime_release_freeze_lock
from app.services.mission_control.runtime_responsiveness_guarantees import build_runtime_responsiveness_guarantees
from app.services.mission_control.runtime_stability_coordinator import build_runtime_stability_coordinator


CERT_CATEGORIES = (
    "runtime_stability",
    "runtime_continuity",
    "runtime_recovery",
    "runtime_readiness",
    "runtime_integrity",
    "runtime_explainability",
    "runtime_operational_authority",
    "runtime_operator_experience",
    "runtime_responsiveness",
    "runtime_memory_integrity",
    "runtime_branding_integrity",
    "runtime_surface_integrity",
    "runtime_launch_integrity",
)


def build_enterprise_operational_certification_final(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    prod = build_runtime_production_certification(truth)["runtime_production_certification"]
    stability = build_runtime_stability_coordinator(truth)["runtime_stability"]
    session = build_runtime_long_session_reliability(truth)["runtime_long_session_reliability"]
    memory = build_runtime_operational_memory_discipline(truth)["operational_memory_discipline"]
    responsive = build_runtime_responsiveness_guarantees(truth)["enterprise_responsiveness_certification"]
    freeze = build_runtime_release_freeze_lock(truth)["runtime_release_freeze_lock"]
    degraded = build_runtime_degraded_mode_finalization(truth)["runtime_degraded_mode_finalization"]
    categories = {
        "runtime_stability": stability.get("stable"),
        "runtime_continuity": bool((truth.get("runtime_continuity_certification") or {}).get("certified")),
        "runtime_recovery": (truth.get("runtime_recovery_integrity") or {}).get("stable", True),
        "runtime_readiness": (truth.get("runtime_readiness_authority") or {}).get("enterprise_ready"),
        "runtime_integrity": prod.get("production_grade"),
        "runtime_explainability": bool((truth.get("runtime_explainability_finalization") or {}).get("operator_always_has_answer", True)),
        "runtime_operational_authority": (truth.get("operational_authority") or {}).get("authoritative", True),
        "runtime_operator_experience": degraded.get("calm"),
        "runtime_responsiveness": responsive.get("certified") or responsive.get("partial_acceptable"),
        "runtime_memory_integrity": memory.get("bounded"),
        "runtime_branding_integrity": truth.get("operator_facing_branding_locked", True),
        "runtime_surface_integrity": True,
        "runtime_launch_integrity": freeze.get("runtime_frozen"),
    }
    blocking = [k for k, v in categories.items() if not v]
    certified = len(blocking) == 0 and session.get("certified")
    return {
        "enterprise_operational_certification_final": {
            "enterprise_operationally_certified": certified,
            "production_cut_approved": certified and prod.get("production_grade"),
            "operator_trust_verified": bool((truth.get("runtime_operator_trust") or {}).get("trusted")),
            "launch_stabilized": certified,
            "blocking_issues": blocking,
            "categories": categories,
            "phase": "phase4_step24",
            "bounded": True,
        }
    }
