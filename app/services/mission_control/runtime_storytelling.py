# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational storytelling from runtime truth (Phase 3 Step 15)."""

from __future__ import annotations

from typing import Any


def build_runtime_stories(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    stories: dict[str, str] = {}

    health = truth.get("enterprise_operational_health") or {}
    overall = str(health.get("overall") or "healthy")
    stories["deployment_reliability"] = (
        f"Deployment posture is {overall} — review deployments panel for project-level detail."
    )

    prov = (truth.get("enterprise_trust_panels") or {}).get("provider_trust") or truth.get("provider_trust") or {}
    if isinstance(prov, dict):
        stories["provider_stability"] = (
            f"Provider trust score {prov.get('score', '—')}; "
            f"{'fallback in use' if prov.get('fallback_used') else 'primary routing stable'}."
        )

    stories["runtime_recovery"] = _recovery_story(truth)
    stories["repair_effectiveness"] = "Repair flows visible in governance timeline and execution chains."
    stories["worker_specialization"] = _worker_story(truth)
    stories["automation_value"] = "Automation packs are operator-approved and governance-visible."
    stories["privacy_posture"] = _privacy_story(truth)
    stories["governance_trust"] = f"Operational trust score {truth.get('operational_trust_score', '—')}."
    stories["operational_continuity"] = _continuity_story(truth)

    return {"stories": stories, "data_derived": True, "actionable": True}


def _recovery_story(truth: dict[str, Any]) -> str:
    conf = truth.get("runtime_confidence") or {}
    rec = conf.get("restart_count") or conf.get("active_recoveries")
    if rec:
        return f"Recovery activity noted — restarts/continuity signals present ({rec})."
    return "No active recovery storms — runtime continuity stable."


def _worker_story(truth: dict[str, Any]) -> str:
    rw = truth.get("runtime_workers") or {}
    n = rw.get("active_count") if isinstance(rw, dict) else 0
    return f"{n} active runtime workers under orchestrator coordination."


def _privacy_story(truth: dict[str, Any]) -> str:
    p = truth.get("privacy") or {}
    mode = p.get("mode") if isinstance(p, dict) else "observe"
    return f"Privacy mode {mode} — egress decisions reflected in governance timeline."


def _continuity_story(truth: dict[str, Any]) -> str:
    c = truth.get("operator_continuity") or {}
    if isinstance(c, dict) and c.get("resume_available"):
        return "Operator continuity snapshot available for seamless resume."
    return "Operator continuity idle — no pending resume required."
