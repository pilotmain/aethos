"""Safe cleanup of stale references (never drops in-flight recovery metadata aggressively)."""

from __future__ import annotations

from typing import Any

from app.execution import execution_plan
from app.orchestration import task_queue
from app.orchestration import task_registry


def cleanup_runtime_state(st: dict[str, Any], *, event_buffer_cap: int = 3000) -> dict[str, Any]:
    """
    Prune orphan queue entries + orphan plans; trim oversized event buffer; drop orphan
    execution-memory buckets; remove checkpoints whose plan is gone.

    Does **not** delete active tasks, sessions, or non-orphan plans.
    """
    out: dict[str, Any] = {}
    out["queues_pruned"] = task_queue.prune_orphan_queue_entries(st)
    out["plans_pruned"] = execution_plan.prune_orphan_plans(st)

    buf = st.get("runtime_event_buffer")
    if isinstance(buf, list) and len(buf) > event_buffer_cap:
        overflow = len(buf) - event_buffer_cap
        st["runtime_event_buffer"] = buf[-event_buffer_cap:]
        out["events_trimmed"] = overflow
    else:
        out["events_trimmed"] = 0

    tr = task_registry.registry(st)
    if not isinstance(tr, dict):
        tr = {}
    ex = execution_plan.execution_root(st)
    mem = ex.get("memory")
    removed_mem = 0
    if isinstance(mem, dict):
        for k in list(mem.keys()):
            if str(k) not in tr:
                del mem[k]
                removed_mem += 1
    out["memory_buckets_pruned"] = removed_mem

    plans = ex.get("plans") or {}
    cps = ex.get("checkpoints")
    removed_cp = 0
    if isinstance(cps, dict) and isinstance(plans, dict):
        for pid in list(cps.keys()):
            if pid not in plans:
                del cps[pid]
                removed_cp += 1
    out["checkpoints_pruned"] = removed_cp

    return out
