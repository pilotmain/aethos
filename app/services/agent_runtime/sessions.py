"""Governed multi-assignment spawn (sessions_spawn tool)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent_team import AgentAssignment
from app.services.agent_runtime.chat_tools import (
    clean_task_for_spawn,
    dedupe_session_specs,
    short_assignment_title,
)
from app.services.agent_runtime.paths import mission_control_md_path
from app.services.agent_runtime.tool_registry import get_tool_record, is_tool_enabled
from app.services.agent_runtime.validation import validate_sessions_spawn
from app.services.agent_runtime.workspace_files import (
    append_timeline_event,
    ensure_seed_files,
    merge_memory_spawn_record,
)
from app.services.agent_team.planner import DEFAULT_ORCHESTRATOR
from app.services.agent_team.service import (
    create_assignment,
    dispatch_assignment,
    get_or_create_default_organization,
)
from app.services.audit_service import audit
from app.services.custom_agents import display_agent_handle, get_custom_agent, normalize_agent_key
from app.services.runtime_capabilities import audit_permission_bypassed, autonomy_test_mode

logger = logging.getLogger(__name__)


def _should_auto_run_deterministic_worker() -> bool:
    """Developer local loop: complete spawned assignments with stub outputs (no LLM)."""
    s = get_settings()
    return (s.nexa_workspace_mode or "").strip().lower() == "developer" and not s.nexa_approvals_enabled


def _dispatch_spawn_children(db: Session, *, user_id: str, created: list[AgentAssignment]) -> None:
    """After spawn rows exist: run workers when a custom agent exists; else waiting_worker."""
    uid = (user_id or "").strip()[:64]
    orch = normalize_agent_key(DEFAULT_ORCHESTRATOR)
    for row in created[1:]:
        ij = row.input_json if isinstance(row.input_json, dict) else {}
        if not str(ij.get("spawn_group_id") or "").strip():
            continue
        db.refresh(row)
        if (row.status or "") not in ("queued", "assigned"):
            continue
        handle = normalize_agent_key(row.assigned_to_handle or "")
        if not handle or handle == orch:
            continue
        agent = get_custom_agent(db, uid, handle)
        if not agent:
            row.status = "waiting_worker"
            row.error = None
            row.output_json = {
                "kind": "waiting_worker",
                "text": (
                    f"No custom agent {display_agent_handle(handle)} yet. "
                    f"Create it, then retry or dispatch assignment #{row.id}."
                )[:8000],
            }
            db.add(row)
            db.commit()
            db.refresh(row)
            continue
        try:
            dispatch_assignment(db, assignment_id=row.id, user_id=uid)
        except Exception:
            logger.exception("spawn dispatch failed assignment_id=%s", row.id)


def _write_mission_control_snapshot(
    *,
    user_id: str,
    spawn_group_id: str,
    goal: str,
    rows: list[AgentAssignment],
) -> None:
    ensure_seed_files()
    lines = [
        "# Mission Control Report",
        "",
        "## Active Agents",
        "",
        "| Agent | Assignment | Status | Notes |",
        "|---|---:|---|---|",
    ]
    for r in rows:
        h = r.assigned_to_handle
        lines.append(f"| @{h} | #{r.id} | {r.status} | spawn `{spawn_group_id}` |")
    lines.extend(
        [
            "",
            "## Spawn goal",
            "",
            goal[:1500],
            "",
            "## Last Updated",
            "",
            f"_spawn group `{spawn_group_id}` — user `{user_id[:32]}`_",
            "",
        ]
    )
    p = mission_control_md_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")


def sessions_spawn(db: Session, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Create a parent meta-assignment (optional) and child assignments for each session spec.
    Persists workspace memory, timeline, and mission_control.md under configured dirs.
    """
    uid = (user_id or "").strip()[:64]
    s = get_settings()
    if not s.nexa_agent_tools_enabled:
        raise RuntimeError("NEXA_AGENT_TOOLS_ENABLED is false")
    if not is_tool_enabled("sessions_spawn"):
        raise RuntimeError("sessions_spawn is not enabled in agent_tools.json")

    err = validate_sessions_spawn(payload)
    if err:
        raise ValueError(err)
    if str(payload.get("requested_by") or "").strip() != uid:
        raise ValueError("requested_by must match the authenticated user")

    session_specs = dedupe_session_specs([dict(x) for x in (payload.get("sessions") or [])])
    if not session_specs:
        raise ValueError("sessions must include at least one valid agent task after deduplication")

    rec = get_tool_record("sessions_spawn")
    pol = payload.get("approval_policy") or {}
    mode = str(pol.get("mode") or "")
    if rec and rec.get("requires_permission") and mode != "plan_only":
        if autonomy_test_mode():
            audit_permission_bypassed(
                db,
                user_id=uid,
                tool="sessions_spawn",
                scope="agent_runtime",
                risk="dev_mode",
                extra={"approval_policy_mode": mode},
            )
        elif not (s.nexa_host_executor_enabled or s.cursor_enabled):
            raise ValueError(
                "This approval policy requires execution backends; enable host executor or IDE-linked "
                "execution, or use approval_policy.mode=plan_only."
            )

    spawn_group_id = "spawn_" + uuid.uuid4().hex[:12]
    goal_raw = str(payload.get("goal") or "").strip()
    goal = clean_task_for_spawn(goal_raw) or goal_raw

    audit(
        db,
        event_type="agent_session.spawn_requested",
        actor="nexa",
        user_id=uid,
        message=f"Spawn requested {spawn_group_id}",
        metadata={"spawn_group_id": spawn_group_id, "goal": goal[:500], "approval_mode": mode},
    )

    org = get_or_create_default_organization(db, uid)
    parent_id = payload.get("parent_assignment_id")
    spawn_parent_created = False
    parent: AgentAssignment | None = None
    if parent_id is not None:
        parent = db.get(AgentAssignment, int(parent_id))
        if parent is None or parent.user_id != uid:
            raise ValueError("parent_assignment_id not found for this user")
    else:
        parent_input: dict[str, Any] = {
            "kind": "spawn_parent",
            "spawn_group_id": spawn_group_id,
            "goal": goal,
            "timebox_minutes": int(payload.get("timebox_minutes") or 60),
            "approval_policy": pol,
        }
        mc = payload.get("mission_contract")
        if isinstance(mc, dict) and mc:
            parent_input["mission_contract"] = mc

        parent = create_assignment(
            db,
            user_id=uid,
            assigned_to_handle=normalize_agent_key(DEFAULT_ORCHESTRATOR),
            title=f"{short_assignment_title(goal)} — [{spawn_group_id}]",
            description=goal[:20_000],
            organization_id=org.id,
            assigned_by_handle="orchestrator",
            input_json=parent_input,
            skip_duplicate_check=True,
        )
        spawn_parent_created = True

    assert parent is not None
    created: list[AgentAssignment] = [parent]
    child_assignments_out: list[dict[str, Any]] = []

    for sess in session_specs:
        handle = normalize_agent_key(str(sess.get("agent_handle") or ""))
        task_raw = str(sess.get("task") or "").strip()
        task = clean_task_for_spawn(task_raw) or task_raw
        title = (task[:500]) if task else short_assignment_title(goal)
        desc = f"Role: {sess.get('role')}\n\n{task}"[:20_000]
        deps_list = sess.get("depends_on") or []
        deps_norm: list[str] = []
        if isinstance(deps_list, list):
            for d in deps_list:
                dk = normalize_agent_key(str(d))
                if dk and dk not in deps_norm:
                    deps_norm.append(dk)
        initial_status = "waiting_worker" if deps_norm else "queued"
        row = create_assignment(
            db,
            user_id=uid,
            assigned_to_handle=handle,
            title=title,
            description=desc,
            organization_id=org.id,
            assigned_by_handle=str(payload.get("requested_by") or "orchestrator")[:64],
            input_json={
                "spawn_group_id": spawn_group_id,
                "role": str(sess.get("role") or "")[:200],
                "task": task,
                "skills": list(sess.get("skills") or []),
                "depends_on": deps_norm,
                "parent_meta_id": parent.id,
            },
            parent_assignment_id=parent.id,
            skip_duplicate_check=True,
            initial_status=initial_status,
        )
        created.append(row)
        child_assignments_out.append(
            {"assignment_id": row.id, "agent_handle": handle, "status": row.status}
        )

    if spawn_parent_created:
        db.refresh(parent)
        parent.status = "completed"
        parent.completed_at = datetime.utcnow()
        parent.output_json = {
            "kind": "spawn_parent",
            "spawn_group_id": spawn_group_id,
            "text": "Mission spawned — child assignments created.",
        }
        db.add(parent)
        db.commit()
        db.refresh(parent)

    if _should_auto_run_deterministic_worker():
        from app.services.swarm.worker import run_mission_workers_until_idle

        run_mission_workers_until_idle(db, user_id=uid, max_iterations=15)
    else:
        _dispatch_spawn_children(db, user_id=uid, created=created)
    for i, row in enumerate(created[1:], start=0):
        db.refresh(row)
        child_assignments_out[i]["status"] = row.status

    ids = [r.id for r in created]
    merge_memory_spawn_record(
        spawn_group_id=spawn_group_id,
        goal=goal,
        assignment_ids=ids,
        user_id=uid,
    )
    append_timeline_event(
        {
            "event": "spawn_created",
            "spawn_group_id": spawn_group_id,
            "user_id": uid,
            "assignment_ids": ids,
        }
    )
    _write_mission_control_snapshot(user_id=uid, spawn_group_id=spawn_group_id, goal=goal, rows=created)

    audit(
        db,
        event_type="agent_session.spawn_created",
        actor="nexa",
        user_id=uid,
        message=f"Spawn created {spawn_group_id} assignments={ids}",
        metadata={"spawn_group_id": spawn_group_id, "assignment_ids": ids},
    )

    return {
        "ok": True,
        "spawn_group_id": spawn_group_id,
        "assignments": child_assignments_out,
        "report_path": str(mission_control_md_path()),
    }
