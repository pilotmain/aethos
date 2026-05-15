"""Named persistent queues in ``aethos.json``."""

from __future__ import annotations

from typing import Any

QUEUE_NAMES = (
    "execution_queue",
    "deployment_queue",
    "agent_queue",
    "channel_queue",
    "recovery_queue",
    "scheduler_queue",
)


def ensure_queue(st: dict[str, Any], name: str) -> list[Any]:
    q = st.setdefault(name, [])
    if not isinstance(q, list):
        st[name] = []
        return st[name]
    return q


def enqueue_task_id(st: dict[str, Any], queue_name: str, task_id: str) -> None:
    q = ensure_queue(st, queue_name)
    if task_id not in q:
        q.append(task_id)


def dequeue_task_id(st: dict[str, Any], queue_name: str) -> str | None:
    q = ensure_queue(st, queue_name)
    if not q:
        return None
    tid = q.pop(0)
    return str(tid) if tid is not None else None


def queue_len(st: dict[str, Any], queue_name: str) -> int:
    return len(ensure_queue(st, queue_name))


def remove_task_id_from_all_queues(st: dict[str, Any], task_id: str) -> None:
    for name in QUEUE_NAMES:
        q = ensure_queue(st, name)
        st[name] = [x for x in q if str(x) != task_id]


def prune_orphan_queue_entries(st: dict[str, Any]) -> int:
    """Remove queue entries whose task ids are missing from ``task_registry``."""
    tr = st.get("task_registry")
    if not isinstance(tr, dict):
        return 0
    removed = 0
    for name in QUEUE_NAMES:
        q = ensure_queue(st, name)
        kept = [x for x in q if str(x) in tr]
        removed += len(q) - len(kept)
        st[name] = kept
    return removed


def dedupe_queue_entries(st: dict[str, Any]) -> int:
    """Remove duplicate task ids within each queue (stable: keep first occurrence)."""
    removed = 0
    for name in QUEUE_NAMES:
        q = ensure_queue(st, name)
        seen: set[str] = set()
        out: list[Any] = []
        for x in q:
            s = str(x)
            if not s:
                removed += 1
                continue
            if s in seen:
                removed += 1
                continue
            seen.add(s)
            out.append(x)
        if len(out) != len(q):
            st[name] = out
    return removed
