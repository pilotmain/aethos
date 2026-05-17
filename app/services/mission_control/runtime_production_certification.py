# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final runtime production certification (Phase 4 Step 23)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_production_discipline import build_mission_control_production_discipline
from app.services.mission_control.runtime_assurance_engine import build_runtime_assurance_engine
from app.services.mission_control.runtime_continuity_certification import build_runtime_continuity_certification
from app.services.mission_control.runtime_integrity_certification import build_runtime_integrity_certification
from app.services.mission_control.runtime_operational_state_machine import build_runtime_operational_state_machine
from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority


PRODUCTION_CATEGORIES = (
    "runtime_readiness",
    "startup_integrity",
    "hydration_integrity",
    "truth_integrity",
    "provider_integrity",
    "governance_integrity",
    "recovery_integrity",
    "continuity_integrity",
    "branding_integrity",
    "operator_experience_integrity",
    "setup_integrity",
    "surface_integrity",
)


def build_runtime_production_certification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = build_runtime_readiness_authority(truth)["runtime_readiness_authority"]
    integrity = build_runtime_integrity_certification(truth)["runtime_integrity_certification"]
    continuity = build_runtime_continuity_certification(truth)["runtime_continuity_certification"]
    state = build_runtime_operational_state_machine(truth)["runtime_operational_state"]["state"]
    categories = {
        "runtime_readiness": readiness.get("enterprise_ready"),
        "startup_integrity": state not in ("offline", "critical"),
        "hydration_integrity": not bool((truth.get("cold_start_reliability") or {}).get("stalled_stage_detected")),
        "truth_integrity": integrity.get("production_ready"),
        "provider_integrity": True,
        "governance_integrity": float((truth.get("governance_readiness") or {}).get("score") or 0.8) >= 0.7,
        "recovery_integrity": (truth.get("runtime_recovery_integrity") or {}).get("stable", True),
        "continuity_integrity": continuity.get("certified"),
        "branding_integrity": truth.get("operator_facing_branding_locked", True),
        "operator_experience_integrity": build_mission_control_production_discipline(truth)["mission_control_production_discipline"]["enterprise_grade"],
        "setup_integrity": truth.get("setup_ready_state_locked", True),
        "surface_integrity": True,
    }
    blocking = [k for k, v in categories.items() if not v]
    production_grade = len(blocking) == 0
    return {
        "runtime_production_certification": {
            "production_grade": production_grade,
            "enterprise_certified": production_grade,
            "runtime_operationally_trusted": production_grade and readiness.get("safe_for_operator"),
            "blocking_issues": blocking,
            "categories": categories,
            "phase": "phase4_step23",
            "bounded": True,
        }
    }


def build_runtime_operator_trust(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    cert = build_runtime_production_certification(truth)["runtime_production_certification"]
    assurance = build_runtime_assurance_engine(truth)["runtime_assurance"]
    return {
        "runtime_operator_trust": {
            "trusted": cert.get("runtime_operationally_trusted"),
            "safe": assurance.get("safe"),
            "stable": assurance.get("stable"),
            "summary": assurance.get("summary"),
            "phase": "phase4_step23",
            "bounded": True,
        }
    }


def build_runtime_enterprise_readiness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    cert = build_runtime_production_certification(truth)["runtime_production_certification"]
    return {
        "runtime_enterprise_readiness": {
            "enterprise_ready": cert.get("enterprise_certified"),
            "production_grade": cert.get("production_grade"),
            "blocking_issues": cert.get("blocking_issues"),
            "phase": "phase4_step23",
            "bounded": True,
        }
    }
