# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 runtime evolution bundle — wires all evolution truth keys."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.adaptive_runtime_intelligence import build_adaptive_runtime_intelligence
from app.services.mission_control.automation_operational_effectiveness import (
    build_automation_adaptation,
    build_automation_execution_quality,
    build_automation_operational_effectiveness,
    build_automation_reliability,
)
from app.services.mission_control.enterprise_operational_maturity import build_enterprise_operational_maturity
from app.services.mission_control.enterprise_operational_memory_evolution import (
    build_continuity_memory,
    build_enterprise_operational_memory,
    build_operational_history_quality,
    build_runtime_evolution_history,
)
from app.services.mission_control.operator_productivity import build_enterprise_productivity_signals
from app.services.mission_control.runtime_evolution_governance import (
    build_adaptation_accountability,
    build_operational_learning_governance,
    build_runtime_evolution_governance,
)
from app.services.mission_control.runtime_evolution_performance import (
    build_hydration_optimization_quality,
    build_operational_scalability_metrics,
    build_runtime_evolution_performance,
)
from app.services.mission_control.runtime_strategy_awareness import build_runtime_strategy_awareness
from app.services.mission_control.strategic_differentiation import (
    build_enterprise_advantage_visibility,
    build_operational_positioning,
    build_strategic_differentiation_summary,
)
from app.services.mission_control.worker_specialization_evolution import build_worker_adaptation_metrics


def apply_runtime_evolution_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Attach Phase 4 Step 1 evolution keys (advisory, bounded, orchestrator-owned)."""
    adaptive = build_adaptive_runtime_intelligence(truth)
    truth["adaptive_runtime_intelligence"] = adaptive
    truth["adaptive_operational_learning"] = adaptive.get("adaptive_operational_learning")
    truth["operational_optimization_signals"] = adaptive.get("operational_optimization_signals")
    truth["runtime_adaptation_history"] = adaptive.get("runtime_adaptation_history")

    worker = build_worker_adaptation_metrics(truth)
    truth["worker_adaptation_metrics"] = worker
    truth.update(worker)

    truth["automation_operational_effectiveness"] = build_automation_operational_effectiveness(truth)
    truth["automation_execution_quality"] = build_automation_execution_quality(truth)
    truth["automation_reliability"] = build_automation_reliability(truth)
    truth["automation_adaptation"] = build_automation_adaptation(truth)

    strategy = build_runtime_strategy_awareness(truth)
    truth["runtime_strategy_awareness"] = strategy
    truth.update(strategy)

    truth["enterprise_operational_memory"] = build_enterprise_operational_memory(truth)
    truth["operational_history_quality"] = build_operational_history_quality(
        truth, memory=truth["enterprise_operational_memory"]
    )
    truth["continuity_memory"] = build_continuity_memory(truth)
    truth["runtime_evolution_history"] = build_runtime_evolution_history()

    truth["runtime_evolution_governance"] = build_runtime_evolution_governance(truth)
    truth["adaptation_accountability"] = build_adaptation_accountability(truth)
    truth["operational_learning_governance"] = build_operational_learning_governance(truth)

    maturity = build_enterprise_operational_maturity(truth)
    truth["enterprise_operational_maturity"] = maturity
    truth.update({k: v for k, v in maturity.items() if k not in truth})

    truth.update(build_enterprise_productivity_signals(truth))

    truth["runtime_evolution_performance"] = build_runtime_evolution_performance(truth)
    truth["operational_scalability_metrics"] = build_operational_scalability_metrics(truth)
    truth["hydration_optimization_quality"] = build_hydration_optimization_quality(truth)

    truth["strategic_differentiation_summary"] = build_strategic_differentiation_summary(truth)
    truth["enterprise_advantage_visibility"] = build_enterprise_advantage_visibility(truth)
    truth["operational_positioning"] = build_operational_positioning(truth)

    from app.services.mission_control.runtime_evolution_step2 import apply_runtime_evolution_step2_to_truth

    apply_runtime_evolution_step2_to_truth(truth, user_id=user_id)
    from app.services.mission_control.runtime_evolution_step3 import apply_runtime_evolution_step3_to_truth

    apply_runtime_evolution_step3_to_truth(truth, user_id=user_id)
    from app.services.mission_control.runtime_evolution_step5 import apply_runtime_evolution_step5_to_truth

    apply_runtime_evolution_step5_to_truth(truth)
    from app.services.mission_control.runtime_evolution_step6 import apply_runtime_evolution_step6_to_truth

    apply_runtime_evolution_step6_to_truth(truth)
    from app.services.mission_control.runtime_evolution_step7 import apply_runtime_evolution_step7_to_truth

    apply_runtime_evolution_step7_to_truth(truth, user_id=user_id)
    from app.services.mission_control.runtime_evolution_step8 import apply_runtime_evolution_step8_to_truth

    apply_runtime_evolution_step8_to_truth(truth, user_id=user_id)
    from app.services.mission_control.runtime_evolution_step9 import apply_runtime_evolution_step9_to_truth

    apply_runtime_evolution_step9_to_truth(truth, user_id=user_id)
    from app.services.mission_control.runtime_evolution_step10 import apply_runtime_evolution_step10_to_truth

    apply_runtime_evolution_step10_to_truth(truth, user_id=user_id)
    from app.services.mission_control.runtime_evolution_step12 import apply_runtime_evolution_step12_to_truth

    apply_runtime_evolution_step12_to_truth(truth, user_id=user_id)
    truth["enterprise_overview"] = build_enterprise_overview(truth)
    return truth


def build_enterprise_overview(truth: dict[str, Any]) -> dict[str, Any]:
    outlook = truth.get("enterprise_operational_outlook") or {}
    eco_out = truth.get("enterprise_ecosystem_outlook") or {}
    return {
        "readiness_score": truth.get("runtime_readiness_score"),
        "maturity": (truth.get("enterprise_operational_posture") or {}).get("overall_posture"),
        "positioning": (truth.get("runtime_ecosystem_positioning") or {}).get("positioning")
        or (truth.get("runtime_strategy_positioning") or {}).get("positioning")
        or (truth.get("operational_positioning") or {}).get("positioning"),
        "strategic_alerts": len((truth.get("strategic_runtime_alerts") or [])),
        "adaptive_signals": len((truth.get("operational_optimization_signals") or [])),
        "coordination_signals": len((truth.get("adaptive_execution_signals") or [])),
        "efficiency_signals": len((truth.get("operational_efficiency_signals") or [])),
        "strategic_insights": len((truth.get("strategic_runtime_insights") or [])),
        "outlook": eco_out.get("outlook") or outlook.get("outlook"),
        "worker_ecosystem": (truth.get("worker_ecosystem_health") or {}).get("status"),
        "ecosystem_health": (truth.get("ecosystem_operational_health") or {}).get("status"),
        "optimization_quality": (truth.get("runtime_optimization_quality") or {}).get("score"),
        "phase": "phase4_step12",
        "setup_ready_state_locked": True,
        "production_cut_ready": True,
        "runtime_operator_experience": True,
        "executive_overview": bool(truth.get("executive_operational_overview")),
        "governance_experience_layer": bool(truth.get("governance_experience_layer")),
        "adaptive_routing": bool(truth.get("adaptive_provider_routing")),
        "identity_locked": bool((truth.get("runtime_identity_lock") or {}).get("locked")),
        "sustained_operation_score": truth.get("sustained_operation_score"),
        "production_ready": (truth.get("production_runtime_posture") or {}).get("ready"),
        "operational_responsiveness_score": (truth.get("operational_responsiveness") or {}).get("score"),
        "cache_hit_rate": (truth.get("runtime_performance_intelligence") or {})
        .get("cache_efficiency", {})
        .get("hit_rate"),
        "intelligent_routing": bool(truth.get("intelligent_routing")),
        "operational_recovery": bool(truth.get("operational_recovery_state")),
        "advisory_count": len(truth.get("strategic_recommendations") or []),
        "runtime_resilience": (truth.get("runtime_resilience") or {}).get("status"),
        "truth_integrity_score": truth.get("truth_integrity_score"),
    }
