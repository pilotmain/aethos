"""Central Dev Agent job planning and creation (orchestrator + payload + policy)."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.agent_job import AgentJobCreate
from app.services.dev_job_payload import merge_dev_payload
from app.services.dev_orchestrator.dev_decision import DevExecutionDecision
from app.services.dev_orchestrator.formatting import format_dev_execution_plan
from app.services.dev_orchestrator.orchestrator import build_dev_execution_plan
from app.services.dev_tools.registry import get_dev_tool
from app.services.project_registry import get_default_project, get_project_by_key


def extract_explicit_dev_tool_request(text: str) -> str | None:
    t = (text or "").lower()

    if "use cursor" in t or "open in cursor" in t or re.search(r"\busing\s+cursor\b", t):
        return "cursor"

    if (
        "use vscode" in t
        or "open in vscode" in t
        or "vs code" in t
        or re.search(r"\busing\s+vs\s*code\b", t)
        or re.search(r"\bin\s+vs\s*code\b", t)
    ):
        return "vscode"

    if "use pycharm" in t or re.search(r"\busing\s+pycharm\b", t):
        return "pycharm"

    if "use intellij" in t or re.search(r"\busing\s+intellij\b", t):
        return "intellij"

    if "use aider" in t or re.search(r"\busing\s+aider\b", t):
        return "aider"

    return None


def _apply_explicit_tool_to_plan(plan: dict[str, Any], project: Any, explicit: str) -> None:
    """Mutates plan: decision, message, payload_fragment.execution_decision."""
    tool = explicit.strip().lower()
    if not get_dev_tool(tool):
        raise ValueError(f"Unknown dev tool `{tool}`. Try `/dev tools`.")

    d: DevExecutionDecision = plan["decision"]
    new_mode = "autonomous_cli" if tool == "aider" else "ide_handoff"
    warnings = list(d.warnings)
    warnings.append(f"Explicit tool request: `{tool}` → mode `{new_mode}`.")
    new_dec = replace(
        d,
        tool_key=tool,
        mode=new_mode,
        reason=f"Explicit tool request ({tool}).",
        warnings=warnings,
    )
    plan["decision"] = new_dec
    pp = plan["project_profile"]
    tp = plan["task_profile"]
    plan["message"] = format_dev_execution_plan(project, pp, tp, new_dec)
    frag = dict(plan["payload_fragment"])
    frag["execution_decision"] = {
        "tool_key": new_dec.tool_key,
        "mode": new_dec.mode,
        "risk_level": new_dec.risk_level,
        "needs_approval": new_dec.needs_approval,
        "reason": new_dec.reason,
        "warnings": list(new_dec.warnings),
    }
    plan["payload_fragment"] = frag


def prepare_dev_job_plan(
    db: Session,
    *,
    user_id: str,
    task_text: str,
    project_key: str | None = None,
    extra_base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = user_id  # reserved for audit / future use
    pk = (project_key or "").strip() or None
    project = get_project_by_key(db, pk) if pk else get_default_project(db)

    if not project:
        raise ValueError("No project configured for Dev Agent.")

    plan = build_dev_execution_plan(project, task_text)
    explicit = extract_explicit_dev_tool_request(task_text)
    if explicit:
        _apply_explicit_tool_to_plan(plan, project, explicit)

    dec: DevExecutionDecision = plan["decision"]
    base: dict[str, Any] = dict(plan["payload_fragment"])
    base.update(extra_base or {})
    payload = merge_dev_payload(base, db, project.key)
    payload["preferred_dev_tool"] = dec.tool_key
    payload["dev_execution_mode"] = dec.mode
    payload["execution_decision"] = {
        "tool_key": dec.tool_key,
        "mode": dec.mode,
        "risk_level": dec.risk_level,
        "needs_approval": dec.needs_approval,
        "reason": dec.reason,
        "warnings": list(dec.warnings),
    }

    return {
        "project": project,
        "plan": plan,
        "payload": payload,
        "message": plan["message"],
    }


def create_planned_dev_job(
    db: Session,
    *,
    user_id: str,
    telegram_chat_id: str | None,
    task_text: str,
    project_key: str | None = None,
    source: str = "telegram",
    title: str | None = None,
    instruction: str | None = None,
    extra_payload: dict[str, Any] | None = None,
    job_service: Any | None = None,
) -> dict[str, Any]:
    from app.services.agent_job_service import AgentJobService

    js = job_service or AgentJobService()
    prepared = prepare_dev_job_plan(
        db,
        user_id=user_id,
        task_text=task_text,
        project_key=project_key,
        extra_base=extra_payload,
    )
    project = prepared["project"]
    payload = prepared["payload"]
    plan = prepared["plan"]
    dec = plan["decision"]

    tit = (title or "").strip() or (task_text or "").strip().split("\n", 1)[0].strip()
    tit = tit[:255] if tit else "Dev Agent task"
    inst = (instruction or task_text or "").strip()

    ac = AgentJobCreate(
        kind="dev_task",
        worker_type="dev_executor",
        title=tit,
        instruction=inst,
        source=source,
        payload_json=payload,
        telegram_chat_id=telegram_chat_id,
    )
    job, pol = js.create_dev_task_with_policy(db, user_id, ac, f"{tit}\n{inst}")
    return {
        "job": job,
        "project": project,
        "plan": plan,
        "message": prepared["message"],
        "policy": pol,
        "agent_job_create": ac,
    }


def format_planned_dev_reply(
    *,
    plan_message: str,
    job_id: int,
    decision: DevExecutionDecision,
    repo_line: str | None = None,
) -> str:
    tail = f"\n\n**Repo (worker):** `{repo_line}`" if repo_line else ""
    return (
        f"{plan_message}\n\n"
        f"Queued Dev Agent job #{job_id}.\n"
        f"Tool: `{decision.tool_key}` · Mode: `{decision.mode}` · Risk: `{decision.risk_level}`\n\n"
        f"Reply `approve job #{job_id}` to queue the worker.{tail}"
    )
