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

    def add(
        kind: str,
        message: str,
        confidence: float,
        *,
        reason: str,
        impact: str,
        next_step: str,
        rec_type: str,
        project_id: str | None = None,
        worker_id: str | None = None,
        provider: str | None = None,
    ) -> None:
        recs.append(
            {
                "kind": kind,
                "type": rec_type,
                "message": message,
                "reason": reason,
                "confidence": confidence,
                "operational_impact": impact,
                "affected_project": project_id,
                "affected_worker": worker_id,
                "affected_provider": provider,
                "suggested_next_step": next_step,
                "advisory": True,
                "requires_approval": True,
            }
        )

    if "provider_instability_trend" in kinds:
        add(
            "recommended_provider_switch",
            "Consider switching provider or enabling fallback.",
            0.72,
            reason="Provider failure trend in runtime events",
            impact="high",
            next_step="Review provider inventory and enable fallback routing",
            rec_type="provider_fallback",
            provider="primary",
        )
    if "retry_pressure_pattern" in kinds:
        add(
            "recommended_retry_strategy",
            "Review retry strategy — queue pressure elevated.",
            0.65,
            reason="Retry pressure pattern detected",
            impact="medium",
            next_step="Reduce concurrent retries or increase backoff",
            rec_type="deployment",
        )
    if "deployment_reliability_trend" in kinds:
        add(
            "recommended_deployment_rollback",
            "Consider deployment rollback after repeated failures.",
            0.7,
            reason="Repeated deployment failures",
            impact="high",
            next_step="Rollback to last known-good deployment",
            rec_type="deployment",
        )
    repair_rate = engine.get("repair_success_rate")
    if repair_rate is not None and repair_rate < 0.5:
        add(
            "recommended_verification_rerun",
            "Rerun verification after repair failures.",
            0.68,
            reason=f"Repair success rate {repair_rate:.0%}",
            impact="medium",
            next_step="Trigger verification workflow",
            rec_type="verification",
        )
    if "workspace_degradation" in kinds:
        add(
            "recommended_workspace_verification",
            "Run workspace verification on low-confidence projects.",
            0.75,
            reason="Workspace confidence drift",
            impact="medium",
            next_step="Scan project registry and refresh confidence",
            rec_type="workspace",
        )
    if "repair_churn" in kinds:
        add(
            "recommended_repair_escalation",
            "Escalate repair flow — churn detected.",
            0.66,
            reason="Multiple active repair contexts",
            impact="high",
            next_step="Consolidate repair to single worker chain",
            rec_type="repair",
        )
    if "plugin_instability" in kinds:
        add(
            "recommended_cleanup",
            "Disable unstable plugins / packs until health recovers.",
            0.6,
            reason="Plugin instability signals",
            impact="medium",
            next_step="Disable automation pack or plugin",
            rec_type="automation_pack",
        )

    s = get_settings()
    if getattr(s, "aethos_local_first_enabled", False):
        add(
            "recommended_privacy_mode",
            "Local-first enabled — external egress limited.",
            0.9,
            reason="Local-first policy active",
            impact="low",
            next_step="Confirm privacy mode in Mission Control",
            rec_type="privacy",
        )

    return recs


def _privacy_mode_label() -> str:
    from app.privacy.privacy_policy import current_privacy_mode

    mode = current_privacy_mode(get_settings())
    return str(mode.value if hasattr(mode, "value") else mode)
