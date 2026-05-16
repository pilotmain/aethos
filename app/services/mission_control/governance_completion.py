# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance completion summaries (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any


def build_governance_operational_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    exp = truth.get("governance_experience") or {}
    tl = truth.get("unified_operational_timeline") or {}
    return {
        "headline": "Governance oversight active — unified timeline authoritative",
        "entry_count": tl.get("entry_count"),
        "searchable": exp.get("searchable", True),
        "integrity": truth.get("governance_integrity"),
        "trust_score": truth.get("operational_trust_score"),
    }


def build_runtime_accountability_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    acc = truth.get("runtime_accountability") or {}
    return {
        "orchestrator_owned": acc.get("orchestrator_owned", True),
        "no_hidden_execution": acc.get("no_hidden_execution", True),
        "payload_within_budget": acc.get("payload_within_budget"),
        "cache_hit_rate": acc.get("truth_cache_hit_rate"),
    }


def build_escalation_operational_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    esc = truth.get("runtime_escalations") or {}
    vis = truth.get("escalation_visibility") or {}
    return {
        "active_count": esc.get("escalation_count", 0),
        "types": esc.get("types_present") or [],
        "explainable": vis.get("explainable", True),
        "grouped": True,
    }
