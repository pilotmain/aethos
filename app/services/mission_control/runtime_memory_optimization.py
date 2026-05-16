# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded runtime memory retention sweeps (Phase 3 Step 13)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def run_memory_optimization_sweep() -> dict[str, int]:
    """Prune worker/workspace operational memory without losing governance integrity."""
    st = load_runtime_state()
    s = get_settings()
    removed = {"deliverables": 0, "continuations": 0, "timeline_buffer": 0, "governance_ws": 0}

    dlim = int(getattr(s, "aethos_worker_deliverable_limit", 200))
    clim = int(getattr(s, "aethos_worker_continuation_limit", 48))
    deliverables = st.get("worker_deliverables")
    if isinstance(deliverables, dict) and len(deliverables) > dlim:
        keys = sorted(deliverables.keys(), key=lambda k: str((deliverables.get(k) or {}).get("created_at") or ""))
        for k in keys[: len(deliverables) - dlim]:
            deliverables.pop(k, None)
            removed["deliverables"] += 1

    conts = st.get("worker_continuations")
    if isinstance(conts, dict) and len(conts) > clim:
        keys = sorted(conts.keys(), key=lambda k: str((conts.get(k) or {}).get("created_at") or ""))
        for k in keys[: len(conts) - clim]:
            conts.pop(k, None)
            removed["continuations"] += 1

    buf = st.get("timeline_append_buffer")
    if isinstance(buf, list) and len(buf) > 64:
        removed["timeline_buffer"] = len(buf) - 64
        del buf[: removed["timeline_buffer"]]

    ws = st.get("workspace_governance_events")
    if isinstance(ws, dict) and len(ws) > 80:
        keys = sorted(ws.keys())
        for k in keys[: len(ws) - 80]:
            ws.pop(k, None)
            removed["governance_ws"] += 1

    save_runtime_state(st)
    return removed
