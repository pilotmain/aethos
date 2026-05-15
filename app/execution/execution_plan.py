"""Persistent execution plans (OpenClaw-style graphs in ``aethos.json``)."""

from __future__ import annotations

import time
import uuid
from typing import Any


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def execution_root(st: dict[str, Any]) -> dict[str, Any]:
    ex = st.setdefault("execution", {})
    if not isinstance(ex, dict):
        st["execution"] = {}
        return st["execution"]
    return ex


def plans(st: dict[str, Any]) -> dict[str, Any]:
    p = execution_root(st).setdefault("plans", {})
    if not isinstance(p, dict):
        execution_root(st)["plans"] = {}
        return execution_root(st)["plans"]
    return p


def create_plan(
    st: dict[str, Any],
    task_id: str,
    steps: list[dict[str, Any]],
    *,
    deployment_stage: str | None = None,
) -> str:
    """
    Create a plan with ``steps`` each having at least ``step_id`` and optional ``depends_on`` (step ids).
    """
    plan_id = str(uuid.uuid4())
    norm_steps: list[dict[str, Any]] = []
    for raw in steps:
        s = dict(raw)
        sid = str(s.get("step_id") or uuid.uuid4())
        s["step_id"] = sid
        s.setdefault("status", "queued")
        s.setdefault("depends_on", [])
        if not isinstance(s["depends_on"], list):
            s["depends_on"] = []
        s.setdefault("retry_count", 0)
        s.setdefault("last_retry_at", None)
        s.setdefault("next_retry_at", None)
        s.setdefault("failure_reason", None)
        s.setdefault("outputs", [])
        s.setdefault("type", str(s.get("type") or "").strip())
        s.setdefault("tool", s.get("tool"))
        s.setdefault("result", None)
        s.setdefault("error", None)
        s.setdefault("created_at", _now_iso())
        s.setdefault("started_at", None)
        s.setdefault("completed_at", None)
        s.setdefault("retryable", True)
        s.setdefault("max_retries", 3)
        norm_steps.append(s)
    row: dict[str, Any] = {
        "plan_id": plan_id,
        "task_id": task_id,
        "status": "active",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "steps": norm_steps,
    }
    if deployment_stage:
        row["deployment_stage"] = deployment_stage
    plans(st)[plan_id] = row
    return plan_id


def get_plan(st: dict[str, Any], plan_id: str) -> dict[str, Any] | None:
    p = plans(st).get(plan_id)
    return p if isinstance(p, dict) else None


def find_plan_id_for_task(st: dict[str, Any], task_id: str) -> str | None:
    for pid, p in plans(st).items():
        if isinstance(p, dict) and str(p.get("task_id")) == task_id:
            return str(pid)
    return None


def get_step(plan: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    for s in plan.get("steps") or []:
        if isinstance(s, dict) and str(s.get("step_id")) == step_id:
            return s
    return None


def update_plan_timestamp(plan: dict[str, Any]) -> None:
    plan["updated_at"] = _now_iso()


def all_steps_terminal(plan: dict[str, Any]) -> bool:
    terminal = frozenset({"completed", "failed", "cancelled"})
    steps = plan.get("steps") or []
    if not steps:
        return False
    for s in steps:
        if not isinstance(s, dict):
            continue
        if str(s.get("status") or "") not in terminal:
            return False
    return True


def any_step_failed(plan: dict[str, Any]) -> bool:
    for s in plan.get("steps") or []:
        if isinstance(s, dict) and str(s.get("status") or "") == "failed":
            return True
    return False


def attach_plan_to_task(st: dict[str, Any], task_id: str, plan_id: str) -> None:
    from app.orchestration import task_registry

    t = task_registry.get_task(st, task_id)
    if not t:
        return
    t["execution_plan_id"] = plan_id
    t.setdefault("execution_lifecycle", "plan")


def prune_orphan_plans(st: dict[str, Any]) -> int:
    """Remove plans whose ``task_id`` is missing from ``task_registry``."""
    tr = st.get("task_registry")
    if not isinstance(tr, dict):
        return 0
    removed = 0
    for pid in list(plans(st).keys()):
        p = plans(st).get(pid)
        if not isinstance(p, dict):
            continue
        tid = str(p.get("task_id") or "")
        if tid not in tr:
            del plans(st)[pid]
            removed += 1
    return removed
