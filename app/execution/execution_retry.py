"""Persistent retry metadata with exponential backoff."""

from __future__ import annotations

import time
from typing import Any

from app.execution import execution_log
from app.execution import execution_plan


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compute_backoff_seconds(retry_count: int, *, base: float = 1.0, cap: float = 300.0) -> float:
    """Exponential backoff: ``base * 2**(retry_count-1)`` capped at ``cap`` (seconds)."""
    if retry_count <= 0:
        return base
    return min(cap, base * (2 ** (retry_count - 1)))


def schedule_step_retry(
    plan: dict[str, Any],
    step: dict[str, Any],
    reason: str,
    *,
    now_ts: float | None = None,
) -> None:
    rc = int(step.get("retry_count") or 0) + 1
    step["retry_count"] = rc
    step["failure_reason"] = reason
    step["last_retry_at"] = _now_iso()
    delay = compute_backoff_seconds(rc)
    now = now_ts if now_ts is not None else time.time()
    step["next_retry_at"] = now + delay  # unix ts for reliable comparisons in tests + runtime
    step["status"] = "retrying"
    execution_plan.update_plan_timestamp(plan)
    execution_log.log_retry_event(
        "retry_scheduled",
        plan_id=str(plan.get("plan_id", "")),
        step_id=str(step.get("step_id", "")),
        retry_count=rc,
        next_retry_at=step["next_retry_at"],
        failure_reason=reason,
    )
