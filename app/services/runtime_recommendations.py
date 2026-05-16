# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded operational recommendations (Phase 3 Step 10)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.operational_intelligence_engine import (
    build_intelligence_signals,
    build_operational_intelligence_engine,
    build_proactive_suggestions,
)


def build_runtime_recommendations(ort: dict[str, Any] | None = None) -> dict[str, Any]:
    engine = build_operational_intelligence_engine(ort)
    signals = engine.get("signals") or []
    recs = _recommendations_from_signals(signals, engine)
    return {
        "recommendations": recs[:12],
        "suggestions": engine.get("suggestions") or [],
        "privacy_mode": _privacy_mode_label(),
    }


def _recommendations_from_signals(
    signals: list[dict[str, Any]],
    engine: dict[str, Any],
) -> list[dict[str, Any]]:
    kinds = {s.get("kind") for s in signals}
    recs: list[dict[str, Any]] = []

    def add(kind: str, message: str, confidence: float) -> None:
        recs.append(
            {
                "kind": kind,
                "message": message,
                "confidence": confidence,
                "advisory": True,
                "requires_approval": True,
            }
        )

    if "provider_instability_trend" in kinds:
        add("recommended_provider_switch", "Consider switching provider or enabling fallback.", 0.72)
    if "retry_pressure_pattern" in kinds:
        add("recommended_retry_strategy", "Review retry strategy — queue pressure elevated.", 0.65)
    if "deployment_reliability_trend" in kinds:
        add("recommended_deployment_rollback", "Consider deployment rollback after repeated failures.", 0.7)
    repair_rate = (engine.get("repair_success_rate") if "repair_success_rate" in engine else None)
    if repair_rate is not None and repair_rate < 0.5:
        add("recommended_verification_rerun", "Rerun verification after repair failures.", 0.68)
    if "workspace_degradation" in kinds:
        add("recommended_workspace_verification", "Run workspace verification on low-confidence projects.", 0.75)
    if "repair_churn" in kinds:
        add("recommended_repair_escalation", "Escalate repair flow — churn detected.", 0.66)
    if "plugin_instability" in kinds:
        add("recommended_cleanup", "Disable unstable plugins / packs until health recovers.", 0.6)

    s = get_settings()
    if getattr(s, "aethos_local_first_enabled", False):
        add("recommended_privacy_mode", "Local-first enabled — external egress limited.", 0.9)

    return recs


def _privacy_mode_label() -> str:
    from app.privacy.privacy_policy import current_privacy_mode

    mode = current_privacy_mode(get_settings())
    return str(mode.value if hasattr(mode, "value") else mode)
