# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 3 — enterprise operational intelligence ecosystem."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.adaptive_runtime_optimization import (
    build_adaptive_runtime_optimization,
    build_operational_efficiency_signals,
    build_runtime_optimization_quality,
)
from app.services.mission_control.ecosystem_operational_strategy import build_ecosystem_operational_strategy
from app.services.mission_control.enterprise_operational_maturity_intelligence import (
    build_adaptive_operational_maturity,
)
from app.services.mission_control.governance_intelligence import build_governance_operational_intelligence
from app.services.mission_control.intelligent_runtime_evolution import build_intelligent_runtime_evolution
from app.services.mission_control.operational_intelligence_ecosystem import build_operational_intelligence_ecosystem
from app.services.mission_control.operational_intelligence_recommendations import enrich_recommendations_ecosystem
from app.services.mission_control.runtime_optimization_performance import (
    build_ecosystem_scalability_quality,
    build_operational_intelligence_responsiveness,
    build_runtime_optimization_performance,
    build_runtime_signal_optimization,
)
from app.services.mission_control.strategic_differentiation import (
    build_enterprise_operational_intelligence_advantage,
    build_operational_optimization_advantage,
    build_runtime_ecosystem_positioning,
)
from app.services.mission_control.strategic_forecast_optimization import build_adaptive_operational_forecasting
from app.services.mission_control.worker_ecosystem_optimization import build_adaptive_worker_ecosystem
from app.runtime.runtime_state import load_runtime_state


def apply_runtime_evolution_step3_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Attach Phase 4 Step 3 truth keys after Steps 1–2."""
    opt = build_adaptive_runtime_optimization(truth)
    truth["adaptive_runtime_optimization"] = opt
    truth["runtime_optimization_quality"] = build_runtime_optimization_quality(truth)
    truth["operational_efficiency_signals"] = build_operational_efficiency_signals(truth)
    st = load_runtime_state()
    truth["runtime_optimization_history"] = list(st.get("runtime_optimization_history") or [])[-12:]

    eco = build_operational_intelligence_ecosystem(truth)
    truth["operational_intelligence_ecosystem"] = eco
    truth["ecosystem_coordination"] = eco.get("ecosystem_coordination")
    truth["ecosystem_operational_health"] = eco.get("ecosystem_operational_health")
    truth["ecosystem_maturity_progression"] = eco.get("ecosystem_maturity_progression")

    worker = build_adaptive_worker_ecosystem(truth)
    truth["adaptive_worker_ecosystem"] = worker
    truth["worker_optimization_quality"] = worker.get("worker_optimization_quality")
    truth["worker_operational_coordination"] = worker.get("worker_operational_coordination")
    truth["worker_ecosystem_maturity"] = worker.get("worker_ecosystem_maturity")

    forecast = build_adaptive_operational_forecasting(truth)
    truth["adaptive_operational_forecasting"] = forecast
    truth["strategic_runtime_projection"] = forecast.get("strategic_runtime_projection")
    truth["enterprise_operational_forecast_quality"] = forecast.get("enterprise_operational_forecast_quality")
    truth["runtime_prediction_confidence"] = forecast.get("runtime_prediction_confidence")

    evolution = build_intelligent_runtime_evolution(truth)
    truth["intelligent_runtime_evolution"] = evolution
    truth["runtime_adaptation_quality"] = evolution.get("runtime_adaptation_quality")
    truth["operational_growth_intelligence"] = evolution.get("operational_growth_intelligence")
    truth["ecosystem_evolution_quality"] = evolution.get("ecosystem_evolution_quality")

    gov = build_governance_operational_intelligence(truth)
    truth["governance_operational_intelligence"] = gov
    truth["intelligent_governance_progression"] = gov.get("intelligent_governance_progression")
    truth["governance_quality_signals"] = gov.get("governance_quality_signals")
    truth["operational_accountability_intelligence"] = gov.get("operational_accountability_intelligence")

    enrich_recommendations_ecosystem(truth)

    strategy = build_ecosystem_operational_strategy(truth)
    truth["ecosystem_operational_strategy"] = strategy
    truth["enterprise_ecosystem_outlook"] = strategy.get("enterprise_ecosystem_outlook")
    truth["operational_ecosystem_health"] = strategy.get("operational_ecosystem_health")
    truth["strategic_ecosystem_projection"] = strategy.get("strategic_ecosystem_projection")

    truth["runtime_optimization_performance"] = build_runtime_optimization_performance(truth)
    truth["ecosystem_scalability_quality"] = build_ecosystem_scalability_quality(truth)
    truth["operational_intelligence_responsiveness"] = build_operational_intelligence_responsiveness(truth)
    truth["runtime_signal_optimization"] = build_runtime_signal_optimization(truth)

    mat = build_adaptive_operational_maturity(truth)
    truth.update(mat)

    truth["enterprise_operational_intelligence_advantage"] = build_enterprise_operational_intelligence_advantage(truth)
    truth["runtime_ecosystem_positioning"] = build_runtime_ecosystem_positioning(truth)
    truth["operational_optimization_advantage"] = build_operational_optimization_advantage(truth)

    truth["enterprise_intelligence"] = build_enterprise_intelligence_summary(truth)
    return truth


def build_enterprise_intelligence_summary(truth: dict[str, Any]) -> dict[str, Any]:
    return {
        "ecosystem_health": (truth.get("ecosystem_operational_health") or {}).get("status"),
        "optimization_quality": (truth.get("runtime_optimization_quality") or {}).get("score"),
        "forecast_confidence": (truth.get("runtime_prediction_confidence") or {}).get("confidence"),
        "governance_intelligence": bool(truth.get("governance_operational_intelligence")),
        "phase": "phase4_step3",
    }
