"""Orchestration boot + high-level coordination."""

from __future__ import annotations

import logging
from typing import Any

from app.orchestration import orchestration_log
from app.orchestration import task_recovery
from app.orchestration import task_scheduler

from app.execution import execution_continuation

_LOG = logging.getLogger(__name__)


def orchestration_boot(st: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Run startup recovery on in-memory state (caller persists).
    Starts background scheduler unless skipped (pytest / env).
    """
    if st is None:
        from app.runtime.runtime_state import load_runtime_state

        st = load_runtime_state()
    rec = task_recovery.recover_orchestration_on_boot(st)
    ex = execution_continuation.recover_execution_on_boot(st)
    orchestration_log.log_orchestration_event(
        "orchestration_boot", recovery_tasks=rec.get("count", 0), execution_resume_steps=ex.get("count", 0)
    )
    task_scheduler.start_scheduler_background()
    _LOG.info("orchestration.boot recovery=%s execution=%s", rec.get("count", 0), ex.get("count", 0))
    return {"orchestration": rec, "execution": ex}
