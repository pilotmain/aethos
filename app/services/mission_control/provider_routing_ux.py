# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator-facing provider routing narratives (Phase 4 Step 21)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_provider_routing import build_routing_decision_explanations
from app.services.mission_control.runtime_routing_visibility import build_routing_explanations


def format_calm_fallback_message(*, provider: str, reason: str | None = None) -> str:
    prov = provider or "an alternate provider"
    base = (
        f"AethOS temporarily routed this request through {prov} "
        "because the primary runtime provider became unavailable."
    )
    if reason:
        return f"{base} {reason}"
    return base


def build_provider_routing_ux(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    routing = truth.get("routing_summary") or {}
    explanations = []
    for raw in build_routing_decision_explanations(truth):
        decision = raw.get("decision") or "routing"
        if decision == "fallback":
            prov = routing.get("fallback_provider") or routing.get("selected_provider") or "an alternate provider"
            msg = format_calm_fallback_message(provider=str(prov), reason=raw.get("reason"))
        elif decision == "local_first":
            msg = "AethOS is using local-first routing — private models are preferred when healthy."
        else:
            msg = raw.get("reason") or "AethOS selected the best available provider for this request."
        explanations.append({"decision": decision, "message": msg, "advisory_only": True})
    return {
        "provider_routing_ux": {
            "explanations": explanations,
            "routing_visibility": build_routing_explanations(truth),
            "local_vs_cloud_summary": _local_cloud_summary(truth),
            "phase": "phase4_step21",
            "bounded": True,
        }
    }


def _local_cloud_summary(truth: dict[str, Any]) -> str:
    mode = str(truth.get("AETHOS_ROUTING_MODE") or truth.get("routing_mode") or "hybrid")
    if mode == "local_only":
        return "Local-only routing — cloud providers are not used unless you change strategy."
    if mode == "cloud_only":
        return "Cloud provider routing — local models are not the default path."
    return "Hybrid routing — AethOS prefers local models when healthy, with cloud fallback when needed."
