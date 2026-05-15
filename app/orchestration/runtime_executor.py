"""Execute orchestration tasks (minimal noop + checkpoint hooks)."""

from __future__ import annotations

from typing import Any

from app.orchestration import orchestration_log
from app.orchestration import task_registry


def execute_task(st: dict[str, Any], task_id: str) -> str:
    """
    Run one task step. Returns terminal state name or ``running`` if more work needed.
    """
    t = task_registry.get_task(st, task_id)
    if not t:
        return "failed"
    typ = str(t.get("type") or "noop")
    if typ == "noop":
        orch = st.setdefault("orchestration", {})
        cp = orch.setdefault("checkpoints", {})
        if isinstance(cp, dict):
            cp[task_id] = {"step": "done", "outputs": t.get("outputs") or []}
        return "completed"
    if typ == "deploy":
        orch = st.setdefault("orchestration", {})
        cp = orch.setdefault("checkpoints", {})
        if isinstance(cp, dict):
            cp[task_id] = {"step": "deployed", "outputs": t.get("outputs") or []}
        deps = st.setdefault("deployments", [])
        if isinstance(deps, list):
            deps.append({"task_id": task_id, "status": "completed", "recovered": False})
        orchestration_log.log_deployments_event("deployment_completed", task_id=task_id, status="completed")
        return "completed"
    # Unknown types: mark failed (parity placeholder until real executors wire in)
    return "failed"
