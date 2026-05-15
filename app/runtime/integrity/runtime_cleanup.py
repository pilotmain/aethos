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
    from app.runtime.backups.runtime_backups import backup_runtime_state_dict

    bk = backup_runtime_state_dict(st, reason="cleanup_runtime_state")
    out["backup"] = bk

    from app.runtime.corruption.runtime_repair import repair_runtime_queues_and_metrics

    out["repair"] = repair_runtime_queues_and_metrics(st)
    out["queues_deduped"] = task_queue.dedupe_queue_entries(st)
    if out["queues_deduped"]:
        m = st.setdefault("runtime_metrics", {})
        if isinstance(m, dict):
            m["queue_dedupe_total"] = int(m.get("queue_dedupe_total") or 0) + int(out["queues_deduped"])
            try:
                from app.runtime.events.runtime_events import emit_runtime_event

                emit_runtime_event(st, "queue_repaired", removed_duplicates=int(out["queues_deduped"]))
            except Exception:
                pass
            from app.orchestration import orchestration_log as _olog

            _olog.append_json_log("queue_repair", "queue_repaired", removed_duplicates=int(out["queues_deduped"]))
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

    rs = st.setdefault("runtime_resilience", {})
    if isinstance(rs, dict):
        from app.runtime.runtime_state import utc_now_iso

        rs["last_cleanup"] = {**out, "ts": utc_now_iso()}
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(
            st,
            "cleanup_completed",
            queues_pruned=int(out.get("queues_pruned") or 0),
            queues_deduped=int(out.get("queues_deduped") or 0),
            plans_pruned=int(out.get("plans_pruned") or 0),
            events_trimmed=int(out.get("events_trimmed") or 0),
        )
    except Exception:
        pass
    from app.orchestration import orchestration_log

    orchestration_log.append_json_log("cleanup", "cleanup_completed", **{k: str(v)[:500] for k, v in out.items()})
    return out
