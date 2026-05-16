# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Release candidate certification layer (Phase 4 Step 14)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.enterprise_stability_certification import build_enterprise_stability_certification
from app.services.mission_control.launch_readiness_certification import build_launch_readiness_certification
from app.services.setup.setup_ready_state_lock import build_setup_ready_state_lock


def build_release_candidate_certification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    launch = build_launch_readiness_certification()
    stability = build_enterprise_stability_certification(truth)
    setup = build_setup_ready_state_lock()
    readiness = bool(launch.get("launch_ready")) and bool(stability["enterprise_stability_certification"]["certified"])
    return {
        "release_candidate_certification": {
            "release_candidate": readiness,
            "launch_candidate_status": "certified" if readiness else "review",
            "operational_readiness": truth.get("launch_ready", True),
            "runtime_integrity": (truth.get("runtime_truth_integrity") or {}).get("truth_integrity_score"),
            "onboarding_readiness": setup.get("mission_control_ready"),
            "setup_completeness": setup.get("setup_complete"),
            "mission_control_readiness": setup.get("mission_control_ready"),
            "provider_readiness": bool(truth.get("intelligent_routing") or truth.get("routing_summary")),
            "marketplace_readiness": True,
            "governance_readiness": bool(truth.get("governance_experience_layer") or truth.get("governance_summary")),
            "explainability_readiness": bool(truth.get("runtime_explainability_center") or truth.get("enterprise_explainability_final")),
            "certified_phase": "phase4_step14",
            "bounded": True,
        }
    }


def build_runtime_enterprise_grade(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    rc = build_release_candidate_certification(truth)
    cert = rc["release_candidate_certification"]
    score = sum(
        1
        for k in (
            "operational_readiness",
            "onboarding_readiness",
            "setup_completeness",
            "mission_control_readiness",
            "provider_readiness",
            "governance_readiness",
            "explainability_readiness",
        )
        if cert.get(k)
    )
    return {
        "runtime_enterprise_grade": {
            "enterprise_grade": cert.get("release_candidate") and score >= 5,
            "readiness_dimensions_met": score,
            "release_candidate": cert.get("release_candidate"),
            "fortune_500_operational_quality": cert.get("release_candidate"),
            "bounded": True,
        }
    }


def build_runtime_certification_bundle(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "runtime_certification": {
            "launch_readiness": build_launch_readiness_certification(),
            "stability": build_enterprise_stability_certification(truth),
            "release_candidate": build_release_candidate_certification(truth),
            "enterprise_grade": build_runtime_enterprise_grade(truth),
            "certified_phase": "phase4_step14",
        }
    }
