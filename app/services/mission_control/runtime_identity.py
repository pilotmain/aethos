# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical AethOS operational identity and terminology (Phase 3 Step 15)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_agents import ORCHESTRATOR_ID

# Unified labels — single vocabulary across Mission Control surfaces.
CANONICAL_LABELS: dict[str, str] = {
    "orchestrator": "AethOS Orchestrator",
    "office": "The Office",
    "runtime": "Runtime",
    "worker": "Runtime Worker",
    "governance": "Governance",
    "provider": "Provider",
    "automation_pack": "Automation Pack",
    "deliverable": "Deliverable",
    "recommendation": "Advisory Recommendation",
    "escalation": "Escalation",
    "continuity": "Operator Continuity",
    "privacy": "Privacy Posture",
    "deployment": "Deployment",
    "repair": "Repair Flow",
}


def build_runtime_identity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "platform": "AethOS",
        "orchestrator_id": ORCHESTRATOR_ID,
        "orchestrator_label": CANONICAL_LABELS["orchestrator"],
        "labels": dict(CANONICAL_LABELS),
        "single_truth_path": True,
        "orchestrator_central": True,
        "terminology_version": "phase3_step15",
        "surfaces": [
            "office",
            "runtime",
            "workers",
            "governance",
            "providers",
            "automation",
            "deliverables",
            "insights",
        ],
        "health_label": _health_label(truth),
        "trust_label": _trust_label(truth),
    }


def _health_label(truth: dict[str, Any]) -> str:
    h = truth.get("enterprise_operational_health") or truth.get("runtime_health") or {}
    return str(h.get("overall") or h.get("status") or "healthy")


def _trust_label(truth: dict[str, Any]) -> str:
    score = truth.get("operational_trust_score")
    if score is None:
        return "unknown"
    s = float(score)
    if s >= 0.85:
        return "high trust"
    if s >= 0.65:
        return "moderate trust"
    return "review trust"
