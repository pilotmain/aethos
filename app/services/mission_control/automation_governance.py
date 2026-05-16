# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Automation pack governance and trust (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.plugins.automation_packs import list_automation_packs_with_health
from app.runtime.runtime_state import load_runtime_state


def build_automation_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    packs = (truth or {}).get("automation_packs") or list_automation_packs_with_health()
    if not isinstance(packs, list):
        packs = []
    st = load_runtime_state()
    execs = st.get("automation_pack_executions") or {}
    history: list[dict[str, Any]] = []
    if isinstance(execs, dict):
        history = [r for r in list(execs.values())[-16:] if isinstance(r, dict)]
    failures = sum(1 for h in history if str(h.get("status") or "").lower() in ("failed", "error"))
    return {
        "pack_count": len(packs),
        "operator_approved": True,
        "execution_history": history[:8],
        "failure_count": failures,
        "retry_visible": True,
        "governance_events": len(history),
    }


def build_automation_trust(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    gov = build_automation_governance(truth)
    failures = int(gov.get("failure_count") or 0)
    score = max(0.5, 1.0 - failures * 0.1)
    return {
        "score": round(score, 3),
        "operator_triggered_only": True,
        "pack_count": gov.get("pack_count"),
    }
