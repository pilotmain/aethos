# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Human-centered operational experience (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any


def build_runtime_focus_mode(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    esc = int(((truth or {}).get("runtime_escalations") or {}).get("escalation_count") or 0)
    return {
        "enabled": False,
        "quiet_mode": False,
        "escalation_only_view": esc > 0,
        "prioritized_feed": True,
    }


def build_operational_calmness_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    calm = (truth or {}).get("runtime_calmness") or {}
    lock = (truth or {}).get("calmness_lock") or {}
    return {
        "calm_score": calm.get("calm_score"),
        "feels_calm": calm.get("feels_calm"),
        "lock_engaged": lock.get("locked") if isinstance(lock, dict) else False,
    }


def build_explainable_runtime_insights(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "routing_explainability": (truth or {}).get("intelligent_routing", {}).get("routing_metadata"),
        "strategic_insights": (truth or {}).get("strategic_runtime_insights") or [],
        "advisory_only": True,
    }


def build_operator_trust_experience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "trust_score": (truth or {}).get("operational_trust_score"),
        "confidence_indicators": (truth or {}).get("runtime_prediction_confidence"),
        "explainability": True,
    }


def build_operational_experience_bundle(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "runtime_focus_mode": build_runtime_focus_mode(truth),
        "operational_calmness_engine": build_operational_calmness_engine(truth),
        "explainable_runtime_insights": build_explainable_runtime_insights(truth),
        "operator_trust_experience": build_operator_trust_experience(truth),
        "signal_over_noise": True,
    }
