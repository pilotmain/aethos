# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise governance experience layer (Phase 4 Step 9)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.governance_experience import build_governance_experience
from app.services.mission_control.mission_control_language_system import translate_term


def build_operational_governance_story(truth: dict[str, Any] | None = None) -> str:
    truth = truth or {}
    trust = truth.get("operational_trust_score")
    esc = (truth.get("runtime_escalations") or {}).get("escalation_count") or 0
    if esc:
        return f"Governance active — {esc} item(s) need operator attention; trust {trust or '—'}."
    return f"Governance steady — unified timeline authoritative; trust {trust or '—'}."


def build_escalation_explanations(truth: dict[str, Any] | None = None) -> list[dict[str, str]]:
    truth = truth or {}
    out: list[dict[str, str]] = []
    for esc in ((truth.get("runtime_escalations") or {}).get("active_escalations") or [])[:6]:
        if not isinstance(esc, dict):
            continue
        out.append(
            {
                "title": translate_term("escalation"),
                "explanation": f"{esc.get('type') or 'issue'} from {esc.get('source') or 'runtime'} — severity {esc.get('severity')}.",
                "severity": str(esc.get("severity") or "medium"),
            }
        )
    return out


def build_trust_narratives(truth: dict[str, Any] | None = None) -> list[str]:
    truth = truth or {}
    lines: list[str] = []
    score = truth.get("operational_trust_score")
    if score is not None:
        lines.append(f"Operational trust at {score} — orchestrator-maintained accountability.")
    gr = truth.get("governance_readiness") or {}
    if isinstance(gr, dict) and gr.get("trust_score") is not None:
        lines.append(f"Governance readiness trust {gr.get('trust_score')}.")
    return lines[:6]


def build_accountability_highlights(truth: dict[str, Any] | None = None) -> list[str]:
    truth = truth or {}
    highlights: list[str] = []
    if truth.get("ownership_trace"):
        highlights.append("Ownership trace available for active work.")
    if (truth.get("governance_experience") or {}).get("accountability_visible"):
        highlights.append("Accountability visible on unified timeline.")
    return highlights[:8]


def build_governance_experience_layer(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    base = build_governance_experience(truth)
    return {
        "governance_experience_layer": {
            "headline": "Enterprise governance — operational history with accountability",
            "governance_narratives": base.get("governance_narratives") or [],
            "governance_posture_summary": {
                "searchable": base.get("searchable"),
                "entry_count": base.get("entry_count"),
                "integrity": base.get("integrity"),
            },
            "continuity_explanation": translate_term("continuity")
            + " preserved through bounded timeline windows and era summaries.",
            "recommendation_explanations": [
                str(n.get("narrative", ""))[:160]
                for n in (base.get("governance_narratives") or [])
                if n.get("area") == "recommendation"
            ][:4],
            "bounded": True,
            "enterprise_readable": True,
        },
        "operational_governance_story": build_operational_governance_story(truth),
        "escalation_explanations": build_escalation_explanations(truth),
        "trust_narratives": build_trust_narratives(truth),
        "accountability_highlights": build_accountability_highlights(truth),
    }
