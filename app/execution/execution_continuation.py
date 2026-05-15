"""Resume execution after restart (plans + steps + deployment metadata)."""

from __future__ import annotations

import logging
from typing import Any

from app.execution import execution_log
from app.execution import execution_plan

_LOG = logging.getLogger(__name__)


def recover_execution_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    """
    Reset interrupted ``running`` steps to ``queued`` so the supervisor can resume.
    Preserves retry metadata and checkpoints.
    """
    events: list[str] = []
    root = execution_plan.execution_root(st)
    for pid, plan in list((root.get("plans") or {}).items()):
        if not isinstance(plan, dict):
            continue
        for s in plan.get("steps") or []:
            if not isinstance(s, dict):
                continue
            if str(s.get("status") or "") == "running":
                s["status"] = "queued"
                events.append(f"step:{pid}:{s.get('step_id')}:resume")
                execution_log.log_execution_event(
                    "execution_resume",
                    plan_id=str(pid),
                    step_id=str(s.get("step_id", "")),
                    status="queued",
                )
        # deployment continuation: bump stage marker if present
        if plan.get("deployment_stage") and isinstance(plan.get("steps"), list):
            plan["deployment_recovery"] = {"resumed": True}
        execution_plan.update_plan_timestamp(plan)
    if events:
        _LOG.info("execution.recovery_boot events=%s", len(events))
    return {"events": events, "count": len(events)}
