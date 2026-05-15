"""Dependency ordering for execution plan steps."""

from __future__ import annotations

from typing import Any


def _completed_ids(plan: dict[str, Any]) -> set[str]:
    done: set[str] = set()
    for s in plan.get("steps") or []:
        if not isinstance(s, dict):
            continue
        if str(s.get("status") or "") == "completed":
            done.add(str(s.get("step_id")))
    return done


def dependencies_satisfied(plan: dict[str, Any], step: dict[str, Any]) -> bool:
    done = _completed_ids(plan)
    for dep in step.get("depends_on") or []:
        if str(dep) not in done:
            return False
    return True


def validate_plan_dependency_dag(plan: dict[str, Any]) -> bool:
    """Return False if dependency graph has a cycle (only edges between known ``step_id``s)."""
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
    ids = {str(s.get("step_id")) for s in steps if s.get("step_id")}
    indeg: dict[str, int] = {i: 0 for i in ids}
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for s in steps:
        sid = str(s.get("step_id"))
        if sid not in indeg:
            continue
        for dep in s.get("depends_on") or []:
            d = str(dep)
            if d not in ids:
                continue
            adj[d].append(sid)
            indeg[sid] += 1
    queue = [i for i in ids if indeg[i] == 0]
    seen = 0
    while queue:
        u = queue.pop()
        seen += 1
        for v in adj.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    return seen == len(ids)


def ready_steps(plan: dict[str, Any], *, now_ts: float | None = None) -> list[dict[str, Any]]:
    """
    Steps eligible to run: ``queued`` with deps satisfied, or ``retrying`` with ``next_retry_at`` elapsed.
    Preserves declaration order.
    """
    import time as _time

    now = now_ts if now_ts is not None else _time.time()
    out: list[dict[str, Any]] = []
    for s in plan.get("steps") or []:
        if not isinstance(s, dict):
            continue
        status = str(s.get("status") or "")
        if status == "queued" and dependencies_satisfied(plan, s):
            out.append(s)
        elif status == "retrying":
            nra = s.get("next_retry_at")
            if nra is None:
                out.append(s)
                continue
            try:
                if isinstance(nra, (int, float)) and float(nra) <= now:
                    out.append(s)
                elif isinstance(nra, str):
                    # ISO Z comparison: parse minimal
                    from datetime import datetime

                    dt = datetime.fromisoformat(nra.replace("Z", "+00:00"))
                    if dt.timestamp() <= now:
                        out.append(s)
            except Exception:
                out.append(s)
    return out


def blocked_steps_waiting(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Steps in ``blocked`` or ``queued`` with unsatisfied deps."""
    out: list[dict[str, Any]] = []
    for s in plan.get("steps") or []:
        if not isinstance(s, dict):
            continue
        status = str(s.get("status") or "")
        if status == "blocked":
            out.append(s)
        elif status == "queued" and not dependencies_satisfied(plan, s):
            out.append(s)
    return out
