# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 2 — adaptive coordination and strategic runtime intelligence."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.adaptive_coordination import (
    build_adaptive_coordination,
    build_adaptive_execution_signals,
    build_coordination_quality,
    build_runtime_balancing,
)
from app.services.mission_control.enterprise_operational_maturity import build_enterprise_operational_maturity
from app.services.mission_control.enterprise_operational_strategy import build_enterprise_operational_strategy
from app.services.mission_control.operational_forecasting import (
    build_enterprise_operational_outlook,
    build_operational_forecasting,
    build_runtime_risk_projection,
    build_scalability_forecasts,
)
from app.services.mission_control.operational_intelligence_recommendations import enrich_recommendations_strategic
from app.services.mission_control.runtime_evolution_memory import build_runtime_evolution_memory
from app.services.mission_control.runtime_intelligence_performance import (
    build_coordination_scalability,
    build_forecasting_efficiency,
    build_operational_signal_efficiency,
    build_runtime_intelligence_performance,
)
from app.services.mission_control.strategic_differentiation import (
    build_enterprise_operational_advantage,
    build_operational_intelligence_advantage,
    build_runtime_strategy_positioning,
)
from app.services.mission_control.strategic_governance import build_strategic_governance
from app.services.mission_control.strategic_runtime_intelligence import (
    build_operational_forecasts,
    build_operational_maturity_projection,
    build_runtime_trajectory,
    build_strategic_runtime_insights,
)
from app.services.mission_control.worker_ecosystem_evolution import (
    build_worker_coordination_quality,
    build_worker_ecosystem_health,
    build_worker_operational_growth,
    build_worker_specialization_map,
)


def apply_runtime_evolution_step2_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Attach Phase 4 Step 2 truth keys after Step 1."""
    coord = build_adaptive_coordination(truth)
    truth["adaptive_coordination"] = coord
    truth["coordination_quality"] = build_coordination_quality(truth)
    truth["runtime_balancing"] = build_runtime_balancing(truth)
    truth["adaptive_execution_signals"] = build_adaptive_execution_signals(truth)

    truth["strategic_runtime_insights"] = build_strategic_runtime_insights(truth)
    truth["operational_forecasts"] = build_operational_forecasts(truth)
    truth["runtime_trajectory"] = build_runtime_trajectory(truth)
    truth["operational_maturity_projection"] = build_operational_maturity_projection(truth)

    truth["worker_ecosystem_health"] = build_worker_ecosystem_health(truth)
    truth["worker_coordination_quality"] = build_worker_coordination_quality(truth)
    truth["worker_specialization_map"] = build_worker_specialization_map(truth)
    truth["worker_operational_growth"] = build_worker_operational_growth(truth)

    truth["operational_forecasting"] = build_operational_forecasting(truth)
    truth["runtime_risk_projection"] = build_runtime_risk_projection(truth)
    truth["scalability_forecasts"] = build_scalability_forecasts(truth)
    truth["enterprise_operational_outlook"] = build_enterprise_operational_outlook(truth)

    truth["runtime_evolution_memory"] = build_runtime_evolution_memory(truth)
    mem = truth["runtime_evolution_memory"]
    truth["operational_progression"] = mem.get("operational_progression")
    truth["enterprise_operational_history"] = mem.get("enterprise_operational_history")
    truth["runtime_growth_patterns"] = mem.get("runtime_growth_patterns")

    gov = build_strategic_governance(truth)
    truth["strategic_governance"] = gov
    truth["governance_maturity_progression"] = gov.get("governance_maturity_progression")
    truth["adaptation_governance_quality"] = gov.get("adaptation_governance_quality")
    truth["operational_trust_evolution"] = gov.get("operational_trust_evolution")

    enrich_recommendations_strategic(truth)

    strategy = build_enterprise_operational_strategy(truth)
    truth["enterprise_operational_strategy"] = strategy
    truth["runtime_maturity_strategy"] = strategy.get("runtime_maturity_strategy")
    truth["operational_scaling_strategy"] = strategy.get("operational_scaling_strategy")
    truth["resilience_strategy"] = strategy.get("resilience_strategy")

    truth["runtime_intelligence_performance"] = build_runtime_intelligence_performance(truth)
    truth["forecasting_efficiency"] = build_forecasting_efficiency(truth)
    truth["coordination_scalability"] = build_coordination_scalability(truth)
    truth["operational_signal_efficiency"] = build_operational_signal_efficiency(truth)

    maturity = build_enterprise_operational_maturity(truth)
    truth["enterprise_operational_maturity"] = maturity
    truth["runtime_resilience_maturity"] = maturity.get("runtime_resilience_maturity")
    truth["ecosystem_maturity"] = maturity.get("ecosystem_maturity")
    truth["strategic_operational_maturity"] = maturity.get("strategic_operational_maturity")

    truth["enterprise_operational_advantage"] = build_enterprise_operational_advantage(truth)
    truth["runtime_strategy_positioning"] = build_runtime_strategy_positioning(truth)
    truth["operational_intelligence_advantage"] = build_operational_intelligence_advantage(truth)

    return truth
