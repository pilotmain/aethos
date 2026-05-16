# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Concise operational narratives derived from runtime truth (Phase 3 Step 15)."""

from __future__ import annotations

from typing import Any


def build_operational_narratives(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    narratives: list[dict[str, str]] = []

    dep = truth.get("deployments") or {}
    if isinstance(dep, dict) and dep.get("summary"):
        narratives.append(
            {
                "area": "deployment",
                "narrative": f"Deployments: {str(dep.get('summary'))[:160]}",
            }
        )

    for esc in ((truth.get("runtime_escalations") or {}).get("active_escalations") or [])[:4]:
        if isinstance(esc, dict):
            narratives.append(
                {
                    "area": "escalation",
                    "narrative": f"{esc.get('type')}: severity {esc.get('severity')} from {esc.get('source')}.",
                }
            )

    routing = truth.get("routing_summary") or {}
    if routing.get("fallback_used"):
        narratives.append(
            {
                "area": "provider_fallback",
                "narrative": f"Provider fallback active — {routing.get('reason') or 'routing adjusted'}.",
            }
        )

    for rec in ((truth.get("runtime_recommendations") or {}).get("recommendations") or [])[:3]:
        if isinstance(rec, dict):
            narratives.append(
                {
                    "area": "recommendation",
                    "narrative": str(rec.get("message") or "")[:140],
                }
            )

    cont = truth.get("operator_continuity") or {}
    if isinstance(cont, dict) and cont.get("resume_available"):
        narratives.append(
            {"area": "continuity", "narrative": "Operator continuity available — prior session can resume."}
        )

    pack_gov = (truth.get("enterprise_trust_panels") or {}).get("automation_governance") or {}
    if isinstance(pack_gov, dict) and pack_gov.get("pack_count"):
        narratives.append(
            {
                "area": "automation",
                "narrative": f"Automation packs governed — {pack_gov.get('pack_count')} packs, operator-triggered runs.",
            }
        )

    return {
        "narratives": narratives[:16],
        "count": len(narratives),
        "concise": True,
        "enterprise_readable": True,
        "bounded": True,
    }


def build_operational_narrative_text(truth: dict[str, Any] | None = None) -> str:
    block = build_operational_narratives(truth)
    lines = [n.get("narrative", "") for n in block.get("narratives") or [] if n.get("narrative")]
    return " ".join(lines[:6])[:500] if lines else "Runtime operational — no active narratives."
