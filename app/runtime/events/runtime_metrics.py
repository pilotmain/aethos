"""Lightweight runtime metrics (scheduler + queues) persisted in ``aethos.json``."""

from __future__ import annotations

from typing import Any

from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso


def metrics_root(st: dict[str, Any]) -> dict[str, Any]:
    m = st.setdefault("runtime_metrics", {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = {}
        return st["runtime_metrics"]
    return m


def bump_scheduler_tick(st: dict[str, Any], *, ticks: int) -> None:
    m = metrics_root(st)
    m["scheduler_ticks"] = int(ticks)
    m["last_scheduler_tick_at"] = utc_now_iso()
    orchestration_log.append_json_log("runtime_metrics", "scheduler_tick", ticks=int(ticks))


def bump_dispatch(st: dict[str, Any], *, terminal: str | None) -> None:
    m = metrics_root(st)
    m["queue_dispatch_total"] = int(m.get("queue_dispatch_total") or 0) + 1
    m["last_dispatch_at"] = utc_now_iso()
    if terminal == "completed":
        m["tasks_completed_total"] = int(m.get("tasks_completed_total") or 0) + 1
    elif terminal == "failed":
        m["tasks_failed_total"] = int(m.get("tasks_failed_total") or 0) + 1
    orchestration_log.append_json_log(
        "runtime_metrics",
        "dispatch",
        terminal=terminal or "",
        dispatch_total=m["queue_dispatch_total"],
    )


def bump_runtime_boot(st: dict[str, Any]) -> None:
    m = metrics_root(st)
    m["runtime_boot_count"] = int(m.get("runtime_boot_count") or 0) + 1
    m["last_boot_at"] = utc_now_iso()
