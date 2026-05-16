# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance timeline experience — grouped eras and story windows (Phase 4 Step 9)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_language_system import translate_term


def _group_entries(entries: list[dict[str, Any]], *, limit: int = 24) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for e in entries[:limit]:
        if not isinstance(e, dict):
            continue
        kind = str(e.get("kind") or "other")
        groups.setdefault(kind, []).append(e)
    return [
        {"kind": k, "count": len(v), "preview": v[0] if v else {}, "entries": v[:4]}
        for k, v in sorted(groups.items(), key=lambda x: -len(x[1]))[:8]
    ]


def build_governance_timeline_experience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    tl = truth.get("unified_operational_timeline") or {}
    entries = list(tl.get("timeline") or tl.get("entries") or [])[:48]
    long_h = truth.get("runtime_long_horizon") or {}
    eras = list(long_h.get("operational_eras") or long_h.get("governance_eras") or [])[:8]
    esc_groups = [
        {
            "title": translate_term("escalation"),
            "items": [
                str(e.get("what") or e.get("narrative") or "")[:120]
                for e in entries
                if str(e.get("kind") or "").lower() in ("escalation", "repair", "risk")
            ][:4],
        }
    ]
    dep_journey = [
        str(e.get("what") or "")[:120]
        for e in entries
        if str(e.get("kind") or "").lower() == "deployment"
    ][:4]
    rec_story = [
        str(e.get("what") or "")[:120]
        for e in entries
        if str(e.get("kind") or "").lower() in ("recommendation", "automation")
    ][:4]
    return {
        "timeline_experience": {
            "headline": "Operational history — grouped for calm reading",
            "entry_count": tl.get("entry_count") or len(entries),
            "human_readable": True,
            "bounded": True,
        },
        "governance_story_windows": _group_entries(entries),
        "escalation_story_groups": esc_groups,
        "operational_era_summaries": [
            {"label": e.get("label") or e.get("id"), "summary": e.get("summary")} for e in eras if isinstance(e, dict)
        ][:8],
        "deployment_journey_summaries": dep_journey,
        "recommendation_storyline": rec_story,
        "continuity_explanation": translate_term("continuity") + " across summarized event windows.",
    }
