"""Lookup and continue spawn groups from persisted AgentAssignment rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.agent_team import AgentAssignment
from app.services.agent_runtime.heartbeat import background_heartbeat
from app.services.agent_runtime.paths import mission_control_md_path
from app.services.agent_runtime.workspace_files import ensure_seed_files
from app.services.agent_team.planner import DEFAULT_ORCHESTRATOR
from app.services.custom_agents import display_agent_handle, normalize_agent_key

_SUMMARY_STATUSES = frozenset(
    {
        "queued",
        "running",
        "waiting_approval",
        "waiting_worker",
        "blocked",
        "completed",
        "failed",
        "cancelled",
        "assigned",
    }
)


def normalize_spawn_group_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    s = s.strip().strip("`\"'")
    if not s.startswith("spawn_"):
        s = "spawn_" + s.removeprefix("spawn_")
    return s[:80]


def _title_tag(spawn_group_id: str) -> str:
    return f"[{spawn_group_id}]"


def _goal_from_title(title: str, spawn_group_id: str) -> str:
    tag = f" — {_title_tag(spawn_group_id)}"
    if tag in title:
        return title.split(tag, 1)[0].strip()
    return ""


def _infer_goal(rows: list[AgentAssignment], spawn_group_id: str) -> str:
    for r in rows:
        ij = r.input_json or {}
        if isinstance(ij, dict) and ij.get("kind") == "spawn_parent":
            g = str(ij.get("goal") or "").strip()
            if len(g) >= 5:
                return g[:2000]
    orch = normalize_agent_key(DEFAULT_ORCHESTRATOR)
    for r in rows:
        if normalize_agent_key(r.assigned_to_handle) == orch:
            g = _goal_from_title(r.title, spawn_group_id)
            if len(g) >= 5:
                return g[:2000]
    for r in rows:
        g = _goal_from_title(r.title, spawn_group_id)
        if len(g) >= 5:
            return g[:2000]
    return ""


def _status_summary(rows: list[AgentAssignment]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        st = (r.status or "unknown").strip().lower()
        if st not in _SUMMARY_STATUSES:
            st = "other"
        counts[st] = counts.get(st, 0) + 1
    return counts


def get_spawn_group_state(
    db: Session, *, user_id: str, spawn_group_id: str
) -> dict[str, Any]:
    """
    Load assignments whose title contains `[spawn_<id>]` for this user.
    """
    uid = (user_id or "").strip()[:64]
    sg = normalize_spawn_group_id(spawn_group_id)
    if not sg.startswith("spawn_"):
        return {"ok": False, "not_found": True, "spawn_group_id": sg, "reason": "invalid id"}

    tag = _title_tag(sg)
    ij = AgentAssignment.input_json
    # Parent row title includes the tag; child rows store spawn_group_id in input_json only.
    rows = list(
        db.scalars(
            select(AgentAssignment)
            .where(
                AgentAssignment.user_id == uid,
                or_(
                    AgentAssignment.title.contains(tag),
                    ij["spawn_group_id"].as_string() == sg,
                ),
            )
            .order_by(AgentAssignment.id.asc())
        ).all()
    )
    if not rows:
        return {"ok": False, "not_found": True, "spawn_group_id": sg}

    goal = _infer_goal(rows, sg)
    summary = _status_summary(rows)
    assignments_out = [
        {
            "id": r.id,
            "assigned_to_handle": r.assigned_to_handle,
            "status": r.status,
            "title": (r.title or "")[:500],
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "error": (r.error or "")[:2000] if r.error else None,
            "output_json": r.output_json if isinstance(r.output_json, dict) else {},
        }
        for r in rows
    ]
    return {
        "ok": True,
        "spawn_group_id": sg,
        "goal": goal,
        "assignments": assignments_out,
        "summary": summary,
    }


def write_mission_control_for_spawn_group(
    *,
    user_id: str,
    spawn_group_id: str,
    goal: str,
    assignments: list[dict[str, Any]],
    last_heartbeat: str | None,
) -> None:
    """Rewrite Mission Control markdown from lookup state + optional heartbeat line."""
    ensure_seed_files()
    lines = [
        "# Mission Control Report",
        "",
        f"**Spawn group:** `{spawn_group_id}`",
        "",
        "## Spawn goal",
        "",
        (goal or "(unknown)")[:1500],
        "",
        "## Active Agents",
        "",
        "| Agent | Assignment | Status | Notes |",
        "|---|---:|---|---|",
    ]
    for a in assignments:
        h = display_agent_handle(str(a.get("assigned_to_handle") or ""))
        aid = a.get("id")
        st = a.get("status") or ""
        lines.append(f"| `{h}` | #{aid} | {st} | spawn `{spawn_group_id}` |")
    lines.extend(["", "## Last heartbeat", ""])
    if last_heartbeat:
        lines.append(last_heartbeat[:1500])
    else:
        lines.append("_None recorded for this group._")
    lines.extend(
        [
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


def continue_spawn_group(
    db: Session, *, user_id: str, spawn_group_id: str
) -> dict[str, Any]:
    """
    Resolve spawn group, record a boss heartbeat scoped to the group, refresh Mission Control.
    """
    state = get_spawn_group_state(db, user_id=user_id, spawn_group_id=spawn_group_id)
    if not state.get("ok"):
        return {**state, "heartbeat": None}

    sg = str(state["spawn_group_id"])
    msg = f"Continuing spawn group {sg}"
    hb = background_heartbeat(
        db,
        user_id=user_id,
        payload={
            "agent_handle": "boss",
            "assignment_id": None,
            "spawn_group_id": sg,
            "status": "running",
            "message": msg,
        },
    )
    hb_line = f"**@{display_agent_handle('boss')}** — {msg} (at `{hb.get('recorded_at')}`)"
    write_mission_control_for_spawn_group(
        user_id=user_id,
        spawn_group_id=sg,
        goal=str(state.get("goal") or ""),
        assignments=list(state.get("assignments") or []),
        last_heartbeat=hb_line,
    )
    return {**state, "heartbeat": hb}
