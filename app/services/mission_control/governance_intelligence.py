# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance operational intelligence (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any


def build_intelligent_governance_progression(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    prog = (truth or {}).get("governance_maturity_progression") or {}
    return {
        **prog,
        "intelligence_mode": "advisory",
        "escalation_prioritization": "severity_ordered",
    }


def build_governance_quality_signals(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    signals: list[dict[str, Any]] = []
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    if esc > 0:
        signals.append({"kind": "escalation_volume", "count": esc, "advisory": True})
    if not (truth.get("governance_experience") or {}).get("searchable"):
        signals.append({"kind": "governance_search", "suggestion": "Enable governance search indexing.", "advisory": True})
    return signals[:6]


def build_operational_accountability_intelligence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "orchestrator_owned": True,
        "accountability_summary": (truth or {}).get("runtime_accountability_summary"),
        "adaptation_accountability": (truth or {}).get("adaptation_accountability"),
    }


def build_governance_operational_intelligence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "intelligent_governance_progression": build_intelligent_governance_progression(truth),
        "governance_quality_signals": build_governance_quality_signals(truth),
        "operational_accountability_intelligence": build_operational_accountability_intelligence(truth),
        "trust_evolution": (truth or {}).get("operational_trust_evolution"),
    }
