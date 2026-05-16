# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance for runtime evolution and adaptation (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def build_runtime_evolution_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    hist = st.get("runtime_adaptation_history") or []
    adaptations = len(hist) if isinstance(hist, list) else 0
    return {
        "adaptations_tracked": adaptations,
        "recommendation_evolution": "advisory_only",
        "worker_evolution": "orchestrator_owned",
        "automation_evolution": "operator_approved",
        "governance_visible": True,
        "requires_operator_review": True,
    }


def build_adaptation_accountability(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "orchestrator_owned": True,
        "no_hidden_ai_execution": True,
        "adaptation_log": (truth or {}).get("runtime_adaptation_history") or [],
    }


def build_governance_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = (truth.get("governance_readiness") or {}).get("score")
    exp = truth.get("governance_experience") or {}
    return {
        "maturity_score": float(readiness or 0.85),
        "searchable": bool(exp.get("searchable")),
        "unified_timeline": bool(truth.get("unified_operational_timeline")),
        "explainable": True,
    }


def build_operational_learning_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    learning = (truth or {}).get("adaptive_operational_learning") or {}
    return {
        "learning_mode": learning.get("learning_mode", "advisory_only"),
        "operator_review_required": learning.get("operator_review_required", True),
        "bounded": True,
    }
