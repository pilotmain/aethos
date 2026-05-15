# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Best-effort repairs for queue shapes and metrics (no task deletion)."""

from __future__ import annotations

from typing import Any

from app.orchestration import task_queue
from app.runtime.runtime_state import utc_now_iso


def repair_runtime_queues_and_metrics(st: dict[str, Any]) -> dict[str, Any]:
    """
    Coerce orchestration queues to lists, normalize ``runtime_metrics`` to a dict.

    Returns a summary dict (caller may persist).
    """
    out: dict[str, Any] = {"queues_coerced": 0, "metrics_coerced": 0}
    for name in task_queue.QUEUE_NAMES:
        q = st.get(name)
        if q is None:
            st[name] = []
            out["queues_coerced"] += 1
            continue
        if not isinstance(q, list):
            st[name] = []
            out["queues_coerced"] += 1
    m = st.get("runtime_metrics")
    if not isinstance(m, dict):
        st["runtime_metrics"] = {}
        out["metrics_coerced"] = 1
    rs = st.setdefault("runtime_resilience", {})
    if isinstance(rs, dict):
        rs["last_queue_repair"] = {"ts": utc_now_iso(), **out}
    if int(out.get("queues_coerced") or 0) or int(out.get("metrics_coerced") or 0):
        from app.orchestration import orchestration_log

        orchestration_log.append_json_log("runtime_corruption", "runtime_corruption_repaired", **out)
    return out
