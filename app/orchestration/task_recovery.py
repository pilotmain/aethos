"""Boot-time queue / task recovery (OpenClaw parity sequence, subset in Phase 1)."""

from __future__ import annotations

import logging
from typing import Any

from app.orchestration import orchestration_log
from app.orchestration import task_queue
from app.orchestration import task_registry

_LOG = logging.getLogger(__name__)


def recover_orchestration_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    """
    After restart: interrupted ``running`` / ``waiting`` tasks move to ``recovering``
    and are re-queued on ``recovery_queue`` for the scheduler/dispatcher.
    """
    events: list[str] = []
    for tid in list(task_registry.registry(st).keys()):
        t = task_registry.get_task(st, str(tid))
        if not t:
            continue
        state = str(t.get("state") or "")
        if state in ("running", "waiting", "retrying"):
            task_registry.update_task_state(st, str(tid), "recovering", recovered_from=state)
            task_queue.enqueue_task_id(st, "recovery_queue", str(tid))
            events.append(f"task:{tid}:recovering")
            orchestration_log.log_recovery_event(
                "task_recovering", task_id=str(tid), previous=state
            )
    if events:
        _LOG.info("orchestration.recovery_boot events=%s", len(events))
    return {"events": events, "count": len(events)}
