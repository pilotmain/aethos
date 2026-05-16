# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 5 — runtime autonomy and operational intelligence."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.governance_intelligence_runtime import (
    build_governance_intelligence_runtime,
)
from app.services.mission_control.intelligent_routing import (
    build_intelligent_routing,
    record_routing_hydration_event,
)
from app.services.mission_control.intelligent_worker_ecosystem import (
    build_intelligent_worker_ecosystem,
)
from app.services.mission_control.operational_continuity_engine import (
    build_operational_continuity_engine,
    record_continuity_hydration_snapshot,
)
from app.services.mission_control.operational_memory_intelligence import (
    build_operational_memory_intelligence,
)
from app.services.mission_control.operational_recovery_engine import (
    build_operational_recovery_state,
)
from app.services.mission_control.operator_trust_experience import (
    build_operational_experience_bundle,
)
from app.services.mission_control.runtime_advisories import build_runtime_advisory_engine
from app.services.mission_control.runtime_awareness import build_runtime_awareness
from app.services.mission_control.strategic_runtime_planning import (
    build_strategic_runtime_planning,
)


def apply_runtime_evolution_step5_to_truth(truth: dict[str, Any]) -> dict[str, Any]:
    """Hydrate Phase 4 Step 5 truth keys (advisory, bounded, explainable)."""
    truth["intelligent_routing"] = build_intelligent_routing(truth)
    truth["adaptive_provider_selection"] = truth["intelligent_routing"].get("adaptive_provider_selection")
    truth["runtime_provider_strategy"] = truth["intelligent_routing"].get("runtime_provider_strategy")
    truth["routing_effectiveness"] = truth["intelligent_routing"].get("routing_effectiveness")
    truth["routing_governance"] = truth["intelligent_routing"].get("routing_governance")

    truth["operational_recovery_state"] = build_operational_recovery_state(truth)
    truth["runtime_stabilization"] = truth["operational_recovery_state"].get("runtime_stabilization")
    truth["degradation_signals"] = truth["operational_recovery_state"].get("degradation_signals")
    truth["recovery_coordination"] = truth["operational_recovery_state"].get("recovery_coordination")
    truth["runtime_resilience_engine"] = truth["operational_recovery_state"].get("runtime_resilience_engine")

    truth["operational_memory_intelligence"] = build_operational_memory_intelligence(truth)
    truth["strategic_operational_memory"] = truth["operational_memory_intelligence"].get(
        "strategic_operational_memory"
    )
    truth["continuity_learning"] = truth["operational_memory_intelligence"].get("continuity_learning")
    truth["provider_operational_history"] = truth["operational_memory_intelligence"].get(
        "provider_operational_history"
    )
    truth["deployment_learning"] = truth["operational_memory_intelligence"].get("deployment_learning")
    truth["worker_specialization_memory"] = truth["operational_memory_intelligence"].get(
        "worker_specialization_memory"
    )

    truth["runtime_awareness"] = build_runtime_awareness(truth)
    truth["enterprise_operational_posture"] = truth["runtime_awareness"].get(
        "enterprise_operational_posture"
    )
    truth["operational_stability_matrix"] = truth["runtime_awareness"].get("operational_stability_matrix")
    truth["runtime_pressure_awareness"] = truth["runtime_awareness"].get("runtime_pressure_awareness")
    truth["governance_posture"] = truth["runtime_awareness"].get("governance_posture")

    exp = build_operational_experience_bundle(truth)
    truth["operational_experience"] = exp
    truth["runtime_focus_mode"] = exp.get("runtime_focus_mode")
    truth["operational_calmness_engine"] = exp.get("operational_calmness_engine")
    truth["explainable_runtime_insights"] = exp.get("explainable_runtime_insights")
    truth["operator_trust_experience"] = exp.get("operator_trust_experience")

    truth["strategic_runtime_planning"] = build_strategic_runtime_planning(truth)
    truth["operational_trajectory_intelligence"] = truth["strategic_runtime_planning"].get(
        "operational_trajectory_intelligence"
    )
    truth["enterprise_scalability_projection"] = truth["strategic_runtime_planning"].get(
        "enterprise_scalability_projection"
    )
    truth["strategic_operational_forecasts"] = truth["strategic_runtime_planning"].get(
        "strategic_operational_forecasts"
    )
    truth["continuity_health_projection"] = truth["strategic_runtime_planning"].get(
        "continuity_health_projection"
    )

    truth["intelligent_worker_ecosystem"] = build_intelligent_worker_ecosystem(truth)
    truth["worker_trust_model"] = truth["intelligent_worker_ecosystem"].get("worker_trust_model")
    truth["worker_coordination_engine"] = truth["intelligent_worker_ecosystem"].get("worker_coordination_engine")
    truth["worker_specialization_intelligence"] = truth["intelligent_worker_ecosystem"].get(
        "worker_specialization_intelligence"
    )
    truth["worker_operational_quality"] = truth["intelligent_worker_ecosystem"].get("worker_operational_quality")

    truth["operational_continuity_engine"] = build_operational_continuity_engine(truth)
    truth["runtime_resume_state"] = truth["operational_continuity_engine"].get("runtime_resume_state")
    truth["workspace_operational_snapshots"] = truth["operational_continuity_engine"].get(
        "workspace_operational_snapshots"
    )
    truth["continuity_recovery_quality"] = truth["operational_continuity_engine"].get(
        "continuity_recovery_quality"
    )
    truth["continuity_integrity"] = truth["operational_continuity_engine"].get("continuity_integrity")

    adv = build_runtime_advisory_engine(truth)
    truth["strategic_recommendations"] = adv.get("strategic_recommendations")
    truth["runtime_advisory_engine"] = adv.get("runtime_advisory_engine")
    truth["recommendation_quality"] = adv.get("recommendation_quality")
    truth["operational_guidance"] = adv.get("operational_guidance")
    truth["enterprise_runtime_advisories"] = adv.get("enterprise_runtime_advisories")

    gov = build_governance_intelligence_runtime(truth)
    truth["governance_intelligence"] = gov
    truth["operational_accountability_engine"] = gov.get("operational_accountability_engine")
    truth["runtime_governance_quality"] = gov.get("runtime_governance_quality")
    truth["explainability_integrity"] = gov.get("explainability_integrity")
    truth["enterprise_governance_visibility"] = gov.get("enterprise_governance_visibility")

    truth["phase4_step5"] = True
    record_routing_hydration_event(truth)
    record_continuity_hydration_snapshot(truth)
    return truth


def build_enterprise_overview_step5(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "phase": "phase4_step5",
        "intelligent_routing": bool(truth.get("intelligent_routing")),
        "operational_recovery": bool(truth.get("operational_recovery_state")),
        "runtime_awareness": bool(truth.get("runtime_awareness")),
        "continuity_engine": bool(truth.get("operational_continuity_engine")),
        "advisory_count": len(truth.get("strategic_recommendations") or []),
    }
