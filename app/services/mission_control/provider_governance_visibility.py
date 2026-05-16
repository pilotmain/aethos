# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Provider governance visibility and trust (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_ownership import build_provider_traces
from app.services.operator_context import build_operator_context_panel


def build_provider_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    prov = (truth or {}).get("providers") or {}
    actions = list((prov.get("recent_actions") or []) if isinstance(prov, dict) else [])
    st = load_runtime_state()
    inv = st.get("provider_inventory") or {}
    providers = (inv.get("providers") or {}) if isinstance(inv, dict) else {}
    failures = sum(1 for a in actions if str(a.get("status") or "").lower() in ("failed", "error"))
    return {
        "recent_actions": actions[:12],
        "inventory_count": len(providers) if isinstance(providers, dict) else 0,
        "failure_count": failures,
        "fallback_visible": True,
        "auth_failures_tracked": failures > 0,
    }


def build_provider_history(*, limit: int = 24) -> dict[str, Any]:
    op = build_operator_context_panel()
    actions = list((op.get("recent_provider_actions") or [])[-limit:])
    traces = build_provider_traces(None)[:limit]
    return {"actions": actions, "traces": traces, "count": len(actions)}


def build_provider_trust(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    gov = build_provider_governance(truth)
    failures = int(gov.get("failure_count") or 0)
    score = max(0.35, 1.0 - failures * 0.08)
    routing = (truth or {}).get("routing_summary") or {}
    if routing.get("fallback_used"):
        score -= 0.05
    return {
        "score": round(max(0.0, min(1.0, score)), 3),
        "fallback_used": bool(routing.get("fallback_used")),
        "recent_failures": failures,
        "degradation_visible": failures > 2,
    }
