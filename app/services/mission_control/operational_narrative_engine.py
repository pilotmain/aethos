# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational narrative engine v2 — cohesive storytelling (Phase 4 Step 9)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_language_system import translate_term
from app.services.mission_control.operational_narratives import build_operational_narratives


def build_runtime_storyline(truth: dict[str, Any] | None = None) -> list[dict[str, str]]:
    truth = truth or {}
    storyline: list[dict[str, str]] = []
    for n in (build_operational_narratives(truth).get("narratives") or [])[:10]:
        if isinstance(n, dict) and n.get("narrative"):
            storyline.append({"chapter": n.get("area", "operations"), "text": str(n["narrative"])[:200]})
    recovery = truth.get("operational_recovery_state") or {}
    if isinstance(recovery, dict) and recovery.get("active"):
        storyline.insert(
            0,
            {
                "chapter": "recovery",
                "text": "Runtime recovery engaged — orchestrator restoring operational continuity.",
            },
        )
    return storyline[:12]


def build_strategic_operational_journey(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    eras = (truth.get("runtime_long_horizon") or {}).get("operational_eras") or []
    return {
        "era_count": len(eras),
        "current_chapter": eras[-1].get("label") if eras and isinstance(eras[-1], dict) else "present",
        "continuity_aware": True,
    }


def build_enterprise_operational_context(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "orchestrator_authority": True,
        "advisory_first": (truth.get("intelligent_routing") or {}).get("advisory_first", True),
        "calmness": (truth.get("calmness_integrity") or {}).get("calm") if isinstance(truth.get("calmness_integrity"), dict) else None,
    }


def build_operational_narratives_v2(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    shifts: list[str] = []
    pressure = (truth.get("operational_pressure") or {}).get("level")
    if pressure and pressure != "low":
        shifts.append(f"Operational load shifted — {translate_term('runtime_pressure')}: {pressure}.")
    dep = truth.get("deployment_summary") or {}
    if isinstance(dep, dict) and dep.get("readiness"):
        shifts.append("Deployment posture updated in enterprise summaries.")
    gov = truth.get("governance_summary") or {}
    if isinstance(gov, dict) and (gov.get("escalations") or 0) > 0:
        shifts.append("Governance timeline reflects new escalation activity.")
    return {
        "operational_narratives_v2": {
            "shifts": shifts[:8],
            "recovery_summary": _recovery_summary(truth),
            "governance_change_summary": _governance_change_summary(truth),
            "improvement_summary": _improvement_summary(truth),
            "deployment_trend_summary": _deployment_trend_summary(truth),
            "continuity_story": translate_term("continuity") + " maintained across bounded history windows.",
            "bounded": True,
        },
        "strategic_operational_journey": build_strategic_operational_journey(truth),
        "runtime_storyline": build_runtime_storyline(truth),
        "enterprise_operational_context": build_enterprise_operational_context(truth),
    }


def _recovery_summary(truth: dict[str, Any]) -> str:
    r = truth.get("operational_recovery_state") or {}
    if isinstance(r, dict) and r.get("active"):
        return "Recovery active — degraded paths under orchestrator supervision."
    return "No active recovery — runtime operating within normal bounds."


def _governance_change_summary(truth: dict[str, Any]) -> str:
    idx = truth.get("governance_operational_index") or {}
    cost = idx.get("governance_query_cost") if isinstance(idx, dict) else None
    return f"Governance index efficient — query cost {cost or 'low'}."


def _improvement_summary(truth: dict[str, Any]) -> str:
    score = truth.get("sustained_operation_score")
    if score is not None:
        return f"Sustained operation score {score} — production convergence on track."
    return "Operational improvements tracked via enterprise summaries."


def _deployment_trend_summary(truth: dict[str, Any]) -> str:
    dep = truth.get("deployments") or {}
    if isinstance(dep, dict) and dep.get("summary"):
        return str(dep.get("summary"))[:160]
    return "Deployment trends stable — see deployment posture summary."
