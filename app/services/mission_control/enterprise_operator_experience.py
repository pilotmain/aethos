# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operator experience — final cohesion surfaces (Phase 3 Step 15)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.governance_experience import build_governance_overview
from app.services.mission_control.operational_calmness import build_operational_quality, build_runtime_calmness
from app.services.mission_control.operational_narratives import build_operational_narrative_text, build_operational_narratives
from app.services.mission_control.runtime_identity import build_runtime_identity
from app.services.mission_control.runtime_storytelling import build_runtime_stories
from app.services.mission_control.worker_runtime_cohesion import build_worker_runtime_cohesion


def build_enterprise_runtime_views(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "runtime_overview": build_runtime_overview(truth),
        "runtime_trust": {
            "operational_trust_score": truth.get("operational_trust_score"),
            "panels": truth.get("enterprise_trust_panels"),
        },
        "runtime_accountability": truth.get("runtime_accountability"),
        "runtime_continuity": truth.get("operator_continuity"),
        "runtime_scalability": truth.get("runtime_scalability_health"),
        "operational_health": truth.get("enterprise_operational_health"),
        "operational_recommendations": truth.get("runtime_recommendations"),
        "governance_oversight": build_governance_overview(truth),
        "worker_operations": build_worker_runtime_cohesion(truth),
        "provider_operations": truth.get("providers"),
    }


def build_runtime_overview(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    identity = build_runtime_identity(truth)
    calm = build_runtime_calmness(truth)
    return {
        "headline": (truth.get("operational_summary") or {}).get("headline")
        if isinstance(truth.get("operational_summary"), dict)
        else f"{identity.get('orchestrator_label')} — {identity.get('health_label')}",
        "identity": identity,
        "trust_score": truth.get("operational_trust_score"),
        "calm_score": calm.get("calm_score"),
        "pressure": truth.get("operational_pressure"),
        "health": truth.get("enterprise_operational_health"),
        "active_workers": ((truth.get("runtime_workers") or {}).get("active_count")),
        "narrative_preview": build_operational_narrative_text(truth)[:200],
    }


def build_enterprise_operator_experience(truth: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "runtime_identity": build_runtime_identity(truth),
        "runtime_overview": build_runtime_overview(truth),
        "operational_narratives": build_operational_narratives(truth),
        "runtime_stories": build_runtime_stories(truth),
        "runtime_calmness": build_runtime_calmness(truth),
        "operational_quality": build_operational_quality(truth),
        "governance_experience": build_governance_overview(truth),
        "worker_cohesion": build_worker_runtime_cohesion(truth, user_id=user_id),
        "enterprise_views": build_enterprise_runtime_views(truth),
        "cohesive": True,
        "single_truth_path": True,
    }
