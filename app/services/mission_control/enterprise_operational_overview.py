# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Executive operational overview — lightweight enterprise surface (Phase 4 Step 9)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_language_system import apply_user_facing_language, translate_term


def build_strategic_runtime_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    outlook = truth.get("enterprise_operational_outlook") or {}
    trajectory = truth.get("operational_trajectory_summary") or {}
    return {
        "outlook": outlook.get("outlook") or outlook.get("summary"),
        "trajectory": trajectory.get("direction") or trajectory.get("summary"),
        "maturity": (truth.get("enterprise_overview") or {}).get("maturity"),
    }


def build_enterprise_operational_story(truth: dict[str, Any] | None = None) -> str:
    truth = truth or {}
    health = (truth.get("operational_summary") or {}).get("health") or "nominal"
    posture = (truth.get("production_runtime_posture") or {}).get("ready")
    return (
        f"Enterprise runtime {translate_term(str(health), fallback=health)} — "
        f"production readiness {'confirmed' if posture else 'in progress'} under orchestrator authority."
    )


def build_executive_operational_overview(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    summaries = truth.get("enterprise_runtime_summaries") or {}
    return apply_user_facing_language(
        {
            "executive_operational_overview": {
                "runtime_posture": summaries.get("operational_summary"),
                "deployment_posture": summaries.get("deployment_summary"),
                "governance_posture": summaries.get("governance_summary"),
                "worker_ecosystem_posture": summaries.get("worker_summary"),
                "provider_ecosystem_posture": summaries.get("provider_summary"),
                "continuity_posture": summaries.get("continuity_summary"),
                "strategic_trajectory": build_strategic_runtime_summary(truth),
                "sustained_operation_score": truth.get("sustained_operation_score"),
                "production_ready": (truth.get("production_runtime_posture") or {}).get("ready"),
            },
            "enterprise_operational_story": build_enterprise_operational_story(truth),
            "strategic_runtime_summary": build_strategic_runtime_summary(truth),
            "enterprise_runtime_posture": truth.get("production_runtime_posture") or truth.get("enterprise_operational_posture"),
            "summary_first": True,
            "bounded": True,
        }
    )
