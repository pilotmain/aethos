# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified governance operator experience (Phase 3 Step 15)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operational_narratives import build_operational_narratives
from app.services.mission_control.runtime_identity import CANONICAL_LABELS


def build_governance_experience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    tl = truth.get("unified_operational_timeline") or {}
    entries = list(tl.get("timeline") or [])[:12]
    esc = truth.get("escalation_visibility") or {}
    narratives = [
        n
        for n in (build_operational_narratives(truth).get("narratives") or [])
        if n.get("area") in ("escalation", "recommendation", "automation", "provider_fallback")
    ][:6]
    return {
        "label": CANONICAL_LABELS["governance"],
        "timeline_preview": entries,
        "entry_count": tl.get("entry_count"),
        "authoritative": tl.get("authoritative"),
        "searchable": True,
        "escalation_summary": esc,
        "governance_narratives": narratives,
        "integrity": truth.get("governance_integrity"),
        "accountability_visible": True,
    }


def build_governance_overview(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    exp = build_governance_experience(truth)
    return {
        "headline": "Governance oversight — unified timeline and accountability",
        "experience": exp,
        "trust_score": truth.get("operational_trust_score") if truth else None,
    }
