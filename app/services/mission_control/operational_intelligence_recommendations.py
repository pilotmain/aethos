# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Strategic enrichment for operational recommendations (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any


def enrich_recommendations_strategic(truth: dict[str, Any]) -> None:
    """Attach strategic context to recommendations — advisory only, in-place on truth."""
    block = truth.get("runtime_recommendations")
    if not isinstance(block, dict):
        return
    traj = (truth.get("runtime_trajectory") or truth.get("operational_trajectory_summary") or {})
    direction = traj.get("direction", "stable")
    maturity = (truth.get("operational_maturity_projection") or {}).get("projected_posture", "maturing")
    for rec in block.get("recommendations") or []:
        if not isinstance(rec, dict):
            continue
        rec.setdefault("operational_trajectory_impact", direction)
        rec.setdefault("strategic_relevance", rec.get("operational_impact", "medium"))
        rec.setdefault("ecosystem_impact", "worker_and_provider_visible")
        rec.setdefault("governance_impact_trend", "visible")
        rec.setdefault("confidence_evolution", maturity)
        rec.setdefault("advisory_only", True)
