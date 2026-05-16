# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime explainability center — unified decision explanations (Phase 4 Step 9)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_language_system import translate_term
from app.services.mission_control.operational_explainability import build_operational_explainability


def build_runtime_decision_explanations(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    routing = truth.get("intelligent_routing") or {}
    out: list[dict[str, Any]] = []
    if routing:
        out.append(
            {
                "topic": "routing",
                "reason": (routing.get("routing_metadata") or {}).get("summary")
                or "Advisory-first routing — orchestrator retains execution authority.",
                "advisory_first": routing.get("advisory_first", True),
            }
        )
    throttle = truth.get("runtime_operational_throttling") or {}
    if isinstance(throttle, dict) and throttle.get("active"):
        out.append(
            {
                "topic": "throttling",
                "reason": translate_term("throttling") + " active to preserve Office responsiveness.",
            }
        )
    return out[:8]


def build_recommendation_explanations(truth: dict[str, Any] | None = None) -> list[dict[str, str]]:
    truth = truth or {}
    lines: list[dict[str, str]] = []
    for rec in (truth.get("strategic_recommendations") or [])[:6]:
        if isinstance(rec, dict):
            lines.append(
                {
                    "message": str(rec.get("message") or rec.get("title") or "")[:160],
                    "why": str(rec.get("reason") or "Advisory recommendation — operator approval required.")[:160],
                }
            )
    return lines


def build_continuity_explanations(truth: dict[str, Any] | None = None) -> list[str]:
    truth = truth or {}
    lines: list[str] = []
    cont = truth.get("operational_continuity_engine") or {}
    if isinstance(cont, dict) and cont.get("continuity_recovery_quality"):
        lines.append(f"Continuity recovery quality: {cont.get('continuity_recovery_quality')}.")
    resume = (truth.get("runtime_resume_state") or {}).get("resume_available")
    if resume:
        lines.append("Session resume available from bounded continuity snapshot.")
    return lines[:6]


def build_worker_transition_explanations(truth: dict[str, Any] | None = None) -> list[str]:
    lifecycle = (truth or {}).get("worker_operational_lifecycle") or {}
    maturity = lifecycle.get("worker_lifecycle_maturity") or {}
    stages = maturity.get("stages") or []
    if stages:
        return [f"Worker lifecycle: {' → '.join(stages[:5])} under orchestrator governance."]
    return ["Worker transitions orchestrator-visible and bounded."]


def build_runtime_explainability_center(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    base = build_operational_explainability(truth)
    return {
        "explainability_center": {
            "headline": "Runtime explainability — why the system chose this posture",
            "concise": True,
            "enterprise_readable": True,
            "bounded": True,
        },
        "runtime_decision_explanations": build_runtime_decision_explanations(truth)
        + list(base.get("explanations") or [])[:8],
        "recommendation_explanations": build_recommendation_explanations(truth),
        "continuity_explanations": build_continuity_explanations(truth),
        "worker_transition_explanations": build_worker_transition_explanations(truth),
        "recovery_explanation": _recovery_explanation(truth),
        "governance_action_explanations": _governance_explanations(truth),
    }


def _recovery_explanation(truth: dict[str, Any]) -> str:
    r = truth.get("operational_recovery_state") or {}
    if isinstance(r, dict) and r.get("active"):
        return "Recovery explains degraded paths and restores orchestrator visibility."
    return "No recovery path active."


def _governance_explanations(truth: dict[str, Any]) -> list[str]:
    story = truth.get("operational_governance_story")
    if story:
        return [str(story)[:200]]
    return ["Governance actions recorded on unified timeline with accountability."]
