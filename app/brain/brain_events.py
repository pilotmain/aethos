# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persist brain routing decisions (Phase 2 Step 7)."""

from __future__ import annotations

import uuid
from collections import deque
from typing import Any

from app.privacy.privacy_policy import current_privacy_mode
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state, save_runtime_state, utc_now_iso

_RECENT: deque[dict[str, Any]] = deque(maxlen=48)


def record_brain_decision(
    *,
    task: str,
    selected_provider: str,
    selected_model: str,
    reason: str,
    local_first: bool = False,
    fallback_used: bool = False,
    privacy_meta: dict[str, Any] | None = None,
    repair_context_id: str | None = None,
    project_id: str | None = None,
    fallback_chain: list[str] | None = None,
    cost_estimate: float | None = None,
) -> dict[str, Any]:
    from app.core.config import get_settings

    s = get_settings()
    mode = current_privacy_mode(s)
    row: dict[str, Any] = {
        "brain_decision_id": str(uuid.uuid4()),
        "task": task,
        "selected_provider": selected_provider,
        "selected_model": selected_model,
        "local_first": bool(local_first),
        "privacy_mode": mode.value,
        "reason": reason,
        "fallback_used": bool(fallback_used),
        "created_at": utc_now_iso(),
        "repair_context_id": repair_context_id,
        "project_id": project_id,
    }
    if fallback_chain:
        row["fallback_chain"] = list(fallback_chain)
    if cost_estimate is not None:
        row["cost_estimate"] = cost_estimate
    if isinstance(privacy_meta, dict):
        if privacy_meta.get("fallback_chain") and not row.get("fallback_chain"):
            row["fallback_chain"] = privacy_meta["fallback_chain"]
        if privacy_meta.get("cost_estimate") is not None and row.get("cost_estimate") is None:
            row["cost_estimate"] = privacy_meta["cost_estimate"]
    if privacy_meta:
        row["privacy"] = {
            "scanned": True,
            "redacted": bool(privacy_meta.get("redactions_applied")),
            "egress_allowed": privacy_meta.get("egress_allowed", True),
            "routing_decision": privacy_meta.get("routing_decision"),
        }
    _RECENT.appendleft(row)
    try:
        from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

        emit_mc_runtime_event(
            "brain_selected",
            selected_provider=selected_provider,
            selected_model=selected_model,
            task=task,
            project_id=project_id,
        )
    except Exception:
        pass
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    hist = st.setdefault("brain_decisions", [])
    if isinstance(hist, list):
        hist.append(row)
        if len(hist) > 200:
            del hist[:-200]
    save_runtime_state(st)
    return row


def recent_brain_decisions(*, limit: int = 12) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 48))
    return list(_RECENT)[:lim]
