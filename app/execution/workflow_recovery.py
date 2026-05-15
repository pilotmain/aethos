"""Workflow-oriented recovery helpers (delegates step reset to execution continuation)."""

from __future__ import annotations

from typing import Any

from app.execution import execution_continuation
from app.execution import execution_plan
from app.orchestration import task_registry


def recover_workflows_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    """Reset ``running`` plan steps so dispatch can resume; returns boot recovery summary."""
    return execution_continuation.recover_execution_on_boot(st)


def workflow_integrity_report(st: dict[str, Any]) -> dict[str, Any]:
    """Lightweight consistency scan for ``aethos doctor`` (read-only)."""
    issues: list[str] = []
    tr = st.get("task_registry") if isinstance(st.get("task_registry"), dict) else {}
    plans_root = execution_plan.execution_root(st).get("plans") or {}
    if not isinstance(plans_root, dict):
        return {"ok": False, "issues": ["execution.plans_not_dict"]}
    for pid, plan in plans_root.items():
        if not isinstance(plan, dict):
            issues.append(f"plan_invalid:{pid}")
            continue
        tid = str(plan.get("task_id") or "")
        if tid and tid not in tr:
            issues.append(f"orphan_plan:{pid}")
        t = task_registry.get_task(st, tid) if tid else None
        if t and t.get("execution_plan_id") and str(t.get("execution_plan_id")) != str(pid):
            issues.append(f"task_plan_mismatch:{tid}")
    return {"ok": len(issues) == 0, "issues": issues}
