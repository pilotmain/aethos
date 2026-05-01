"""
Aggregated Mission Control **runtime state** for dynamic UI (Nexa Next).

Maps existing orchestration assignments into a stable ``missions`` / ``tasks`` shape until
dedicated ``missions`` / ``mission_tasks`` tables exist.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nexa_next_runtime import NexaArtifact, NexaMission, NexaMissionTask
from app.services.events.bus import list_events
from app.services.mission_control.read_model import build_mission_control_summary

# Ephemeral streams (privacy audit / provider gateway) until those are persisted.
STATE: dict[str, Any] = {
    "privacy_events": [],
    "provider_events": [],
    "last_updated": None,
}


def add_privacy_event(event: dict[str, Any]) -> None:
    STATE["privacy_events"].append(event)


def add_provider_event(event: dict[str, Any]) -> None:
    STATE["provider_events"].append(event)


def update_state(result: list[dict[str, Any]]) -> None:
    _ = result
    STATE["last_updated"] = datetime.now(timezone.utc).isoformat()


def build_execution_snapshot(db: Session, *, user_id: str | None = None) -> dict[str, Any]:
    """Mission Control execution view: DB-backed missions/tasks/artifacts + bus + ephemeral streams."""
    q = select(NexaMission).order_by(NexaMission.created_at.desc())
    if user_id:
        q = q.where(NexaMission.user_id == user_id)
    mission_rows = list(db.scalars(q).all())

    missions_out = []
    for m in mission_rows:
        it = getattr(m, "input_text", None)
        if it and len(it) > 5000:
            it = it[:5000] + "…"
        missions_out.append(
            {
                "id": m.id,
                "user_id": m.user_id,
                "title": m.title,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "input_text": it,
            }
        )

    mids = [m.id for m in mission_rows]
    tasks_out: list[dict[str, Any]] = []
    artifacts_out: list[dict[str, Any]] = []
    if mids:
        task_rows = db.scalars(select(NexaMissionTask).where(NexaMissionTask.mission_id.in_(mids))).all()
        tasks_out = [
            {
                "id": t.id,
                "mission_id": t.mission_id,
                "agent_handle": t.agent_handle,
                "role": t.role,
                "task": t.task,
                "status": t.status,
                "depends_on": t.depends_on or [],
                "output": t.output_json,
            }
            for t in task_rows
        ]
        art_rows = db.scalars(select(NexaArtifact).where(NexaArtifact.mission_id.in_(mids))).all()
        artifacts_out = [
            {
                "id": a.id,
                "mission_id": a.mission_id,
                "agent": a.agent_handle,
                "artifact": a.artifact_json,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in art_rows
        ]

    return {
        "missions": missions_out,
        "tasks": tasks_out,
        "artifacts": artifacts_out,
        "events": list_events(),
        "privacy_events": list(STATE["privacy_events"]),
        "provider_events": list(STATE["provider_events"]),
        "last_updated": STATE.get("last_updated"),
    }


def build_mission_control_runtime_state(db: Session, user_id: str, *, hours: int = 24) -> dict[str, Any]:
    """Shape expected by ``GET /mission-control/state`` — live-backed, no static mocks."""
    summary = build_mission_control_summary(db, user_id, hours=hours)
    orch = summary.get("orchestration") or {}
    assigns: list[dict[str, Any]] = list(orch.get("assignments") or [])

    missions_by_spawn: dict[str, list[dict[str, Any]]] = defaultdict(list)
    loose: list[dict[str, Any]] = []
    for a in assigns:
        ij = a.get("input_json") if isinstance(a.get("input_json"), dict) else {}
        sg = str(ij.get("spawn_group_id") or "").strip()
        row = {
            "assignment_id": a.get("id"),
            "agent_handle": a.get("assigned_to_handle"),
            "title": a.get("title"),
            "status": a.get("status"),
            "spawn_group_id": sg or None,
        }
        if sg:
            missions_by_spawn[sg].append(row)
        else:
            loose.append(row)

    missions_out = [
        {"spawn_group_id": sg, "tasks": rows, "kind": "spawn_group"}
        for sg, rows in sorted(missions_by_spawn.items(), key=lambda x: x[0])
    ]
    if loose:
        missions_out.append({"spawn_group_id": None, "tasks": loose, "kind": "ungrouped"})

    agents = [
        {
            "handle": a.get("assigned_to_handle"),
            "assignment_id": a.get("id"),
            "status": a.get("status"),
        }
        for a in assigns
    ]

    tasks = [
        {
            "id": a.get("id"),
            "title": a.get("title"),
            "status": a.get("status"),
            "agent_handle": a.get("assigned_to_handle"),
            "spawn_group_id": (a.get("input_json") or {}).get("spawn_group_id")
            if isinstance(a.get("input_json"), dict)
            else None,
        }
        for a in assigns
    ]

    return {
        "missions": missions_out,
        "agents": agents,
        "tasks": tasks,
        "events": [],
        "artifacts": [],
        "privacy_events": [],
        "hours": summary.get("hours"),
        "generated_at": summary.get("overview") is not None,
        "legacy_summary_window": {"hours": hours},
    }
