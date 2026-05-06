"""Mission Control manual cleanup — assignments, jobs, reports, spawn groups, custom agents."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.models.agent_job import AgentJob
from app.models.agent_team import AgentAssignment
from app.services.agent_runtime.defaults import default_agent_status_json, default_memory_json
from app.services.agent_runtime.paths import (
    agent_status_json_path,
    heartbeats_json_path,
    memory_json_path,
    mission_control_md_path,
    timeline_jsonl_path,
    ui_update_event_path,
)
from app.services.agent_runtime.spawn_state import normalize_spawn_group_id
from app.services.agent_runtime.workspace_files import (
    _atomic_write,
    atomic_write_json,
    read_json_file,
)
from app.services.audit_service import audit
from app.services.custom_agents import delete_custom_agent, get_custom_agent, list_custom_agents, normalize_agent_key

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_mission_control_markdown_template() -> str:
    ts = _now_iso()
    return (
        "# Mission Control Report\n\n"
        "No active missions.\n\n"
        "## Active Agents\n\n"
        "None.\n\n"
        "## Last Updated\n\n"
        f"{ts}\n"
    )


def assignment_hidden_mc(row: AgentAssignment | dict[str, Any]) -> bool:
    if isinstance(row, dict):
        ij = row.get("input_json") or {}
    else:
        ij = row.input_json or {}
    if not isinstance(ij, dict):
        return False
    return bool(ij.get("hidden_from_mission_control"))


def job_dismissed_mc(job: AgentJob) -> bool:
    pl = job.payload_json or {}
    if not isinstance(pl, dict):
        return False
    return bool(pl.get("dismissed_from_mission_control"))


def _title_tag(spawn_group_id: str) -> str:
    return f"[{spawn_group_id}]"


def _assignment_matches_spawn_group(row: AgentAssignment, sg: str) -> bool:
    tag = _title_tag(sg)
    if tag in (row.title or ""):
        return True
    ij = row.input_json or {}
    if isinstance(ij, dict):
        raw = ij.get("spawn_group_id")
        if isinstance(raw, str) and normalize_spawn_group_id(raw) == sg:
            return True
    return False


def _soft_hide_assignment(row: AgentAssignment) -> None:
    ij = dict(row.input_json or {})
    ij["hidden_from_mission_control"] = True
    row.input_json = ij
    # JSON columns need explicit change notification on some backends (e.g. Postgres).
    flag_modified(row, "input_json")


def cancel_assignment(db: Session, *, user_id: str, assignment_id: int) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    row = db.get(AgentAssignment, assignment_id)
    if row is None or row.user_id != uid:
        return {"ok": False, "error": "not_found"}
    row.status = "cancelled"
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type="mission_control.assignment.cancelled",
        actor="aethos",
        user_id=uid,
        message=f"Cancelled assignment #{assignment_id}",
        metadata={"assignment_id": assignment_id},
    )
    return {"ok": True, "assignment_id": assignment_id, "action": "cancelled"}


def delete_or_hide_assignment(
    db: Session, *, user_id: str, assignment_id: int, hard_delete: bool | None = None
) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    settings = get_settings()
    allow_hard = bool(settings.nexa_dev_allow_hard_delete)
    do_hard = bool(hard_delete) and allow_hard

    row = db.get(AgentAssignment, assignment_id)
    if row is None or row.user_id != uid:
        return {"ok": False, "error": "not_found"}

    if do_hard:
        db.delete(row)
        db.commit()
        audit(
            db,
            event_type="mission_control.assignment.hidden",
            actor="aethos",
            user_id=uid,
            message=f"Hard-deleted assignment #{assignment_id}",
            metadata={"assignment_id": assignment_id, "hard_delete": True},
        )
        logger.info(
            "mission_control assignment hard_deleted assignment_id=%s user_prefix=%s",
            assignment_id,
            uid[:20],
        )
        return {"ok": True, "assignment_id": assignment_id, "action": "deleted"}

    row.status = "cancelled"
    _soft_hide_assignment(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type="mission_control.assignment.hidden",
        actor="aethos",
        user_id=uid,
        message=f"Hidden assignment #{assignment_id}",
        metadata={"assignment_id": assignment_id, "hard_delete": False},
    )
    logger.info(
        "mission_control assignment hidden assignment_id=%s user_prefix=%s",
        assignment_id,
        uid[:20],
    )
    return {"ok": True, "assignment_id": assignment_id, "action": "hidden"}


def _prune_memory_for_spawn(db: Session, *, user_id: str, sg: str, assignment_ids: list[int]) -> None:
    path = memory_json_path()
    mem = read_json_file(path, default_memory_json())
    sg_map = mem.setdefault("spawn_groups", {})
    if sg in sg_map:
        del sg_map[sg]
    assigns = mem.setdefault("assignments", {})
    for aid in assignment_ids:
        assigns.pop(str(aid), None)
    mem["last_updated_at"] = _now_iso()
    atomic_write_json(path, mem)


def _prune_heartbeats_for_spawn(sg: str) -> None:
    p = heartbeats_json_path()
    data = read_json_file(p, {"version": "1.0", "heartbeats": {}})
    hb = data.setdefault("heartbeats", {})
    drop_keys: list[str] = []
    for k, v in hb.items():
        if not isinstance(v, dict):
            continue
        vsg = v.get("spawn_group_id")
        if vsg is None or str(vsg).strip() == "":
            continue
        if normalize_spawn_group_id(str(vsg)) == sg:
            drop_keys.append(k)
    for k in drop_keys:
        hb.pop(k, None)
    data["last_updated_at"] = _now_iso()
    atomic_write_json(p, data)


def clear_spawn_group(
    db: Session, *, user_id: str, spawn_group_id: str
) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    sg = normalize_spawn_group_id(spawn_group_id)
    if not sg.startswith("spawn_"):
        return {"ok": False, "error": "invalid_spawn_group_id", "spawn_group_id": sg}

    rows = list(
        db.scalars(
            select(AgentAssignment).where(AgentAssignment.user_id == uid).order_by(AgentAssignment.id.asc())
        ).all()
    )
    touched: list[AgentAssignment] = [r for r in rows if _assignment_matches_spawn_group(r, sg)]
    cleared_ids: list[int] = []
    for r in touched:
        r.status = "cancelled"
        _soft_hide_assignment(r)
        db.add(r)
        cleared_ids.append(r.id)
    db.commit()

    _prune_memory_for_spawn(db, user_id=uid, sg=sg, assignment_ids=cleared_ids)
    _prune_heartbeats_for_spawn(sg)

    mc = mission_control_md_path()
    _atomic_write(mc, clean_mission_control_markdown_template())

    ev = ui_update_event_path()
    atomic_write_json(ev, {"kind": "mission_control", "event": "spawn_group_cleared", "spawn_group_id": sg, "at": _now_iso()})

    audit(
        db,
        event_type="mission_control.spawn_group.cleared",
        actor="aethos",
        user_id=uid,
        message=f"Cleared spawn group {sg}",
        metadata={"spawn_group_id": sg, "assignment_ids": cleared_ids},
    )
    return {"ok": True, "spawn_group_id": sg, "cleared_assignments": cleared_ids}


def clear_workspace_reports(db: Session, *, user_id: str) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    cleared: list[str] = []

    mc = mission_control_md_path()
    _atomic_write(mc, clean_mission_control_markdown_template())
    cleared.append("mission_control.md")

    tl = timeline_jsonl_path()
    tl.parent.mkdir(parents=True, exist_ok=True)
    tl.write_text("", encoding="utf-8")
    cleared.append("timeline.jsonl")

    st_path = agent_status_json_path()
    atomic_write_json(st_path, default_agent_status_json())
    cleared.append("agent_status.json")

    ev = ui_update_event_path()
    atomic_write_json(ev, {"kind": "mission_control", "event": "reports_cleared", "at": _now_iso()})

    audit(
        db,
        event_type="mission_control.report.cleared",
        actor="aethos",
        user_id=uid,
        message="Cleared workspace report files",
        metadata={"cleared": cleared},
    )
    return {"ok": True, "cleared": cleared}


def dismiss_agent_job(db: Session, *, user_id: str, job_id: int) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    row = db.get(AgentJob, job_id)
    if row is None or row.user_id != uid:
        return {"ok": False, "error": "not_found"}
    pl = dict(row.payload_json or {})
    pl["dismissed_from_mission_control"] = True
    pl["dismissed_from_mission_control_at"] = _now_iso()
    row.payload_json = pl
    flag_modified(row, "payload_json")
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type="mission_control.job.dismissed",
        actor="aethos",
        user_id=uid,
        job_id=job_id,
        message=f"Dismissed job #{job_id} from Mission Control",
        metadata={"job_id": job_id},
    )
    return {"ok": True, "job_id": job_id, "dismissed": True}


def delete_or_hide_agent_job(
    db: Session, *, user_id: str, job_id: int, hard_delete: bool | None = None
) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    settings = get_settings()
    allow_hard = bool(settings.nexa_dev_allow_hard_delete)
    do_hard = bool(hard_delete) and allow_hard

    row = db.get(AgentJob, job_id)
    if row is None or row.user_id != uid:
        return {"ok": False, "error": "not_found"}

    if do_hard:
        db.execute(sql_delete(AgentJob).where(AgentJob.id == job_id, AgentJob.user_id == uid))
        db.commit()
        audit(
            db,
            event_type="mission_control.job.dismissed",
            actor="aethos",
            user_id=uid,
            job_id=job_id,
            message=f"Hard-deleted job #{job_id}",
            metadata={"job_id": job_id, "hard_delete": True},
        )
        logger.info(
            "mission_control job hard_deleted job_id=%s user_prefix=%s",
            job_id,
            uid[:20],
        )
        return {"ok": True, "job_id": job_id, "action": "deleted"}

    out = dismiss_agent_job(db, user_id=uid, job_id=job_id)
    if out.get("ok"):
        logger.info(
            "mission_control job dismissed job_id=%s user_prefix=%s",
            job_id,
            uid[:20],
        )
    return out


def mission_control_delete_custom_agent(db: Session, *, user_id: str, handle: str) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    k = normalize_agent_key(handle.strip().lstrip("@"))
    if not get_custom_agent(db, uid, k):
        return {"ok": False, "error": "not_found"}
    delete_custom_agent(db, uid, k)
    audit(
        db,
        event_type="mission_control.custom_agent.deleted",
        actor="aethos",
        user_id=uid,
        message=f"Disabled custom agent @{k} from Mission Control",
        metadata={"handle": k},
    )
    return {"ok": True, "handle": k, "action": "disabled"}


def reset_mission_control(
    db: Session,
    *,
    user_id: str,
    include_custom_agents: bool = False,
    hard_delete: bool = False,
) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    settings = get_settings()
    allow_hard = bool(settings.nexa_dev_allow_hard_delete)
    do_hard = bool(hard_delete) and allow_hard

    assignments_cleared = 0
    rows = list(db.scalars(select(AgentAssignment).where(AgentAssignment.user_id == uid)).all())
    for r in rows:
        if assignment_hidden_mc(r):
            continue
        if do_hard:
            db.delete(r)
        else:
            r.status = "cancelled"
            _soft_hide_assignment(r)
            db.add(r)
        assignments_cleared += 1
    db.commit()

    jobs_dismissed = 0
    job_rows = list(db.scalars(select(AgentJob).where(AgentJob.user_id == uid)).all())
    for j in job_rows:
        if job_dismissed_mc(j):
            continue
        if do_hard:
            db.delete(j)
        else:
            pl = dict(j.payload_json or {})
            pl["dismissed_from_mission_control"] = True
            pl["dismissed_from_mission_control_at"] = _now_iso()
            j.payload_json = pl
            flag_modified(j, "payload_json")
            db.add(j)
        jobs_dismissed += 1
    db.commit()

    report_res = clear_workspace_reports(db, user_id=uid)
    reports_cleared = bool(report_res.get("ok"))

    custom_agents_changed = 0
    if include_custom_agents:
        for row in list_custom_agents(db, uid):
            k = str(row.agent_key)
            row.is_active = False
            db.add(row)
            custom_agents_changed += 1
        db.commit()

    from app.services.mission_control.ui_state import clear_attention_dismissals

    clear_attention_dismissals(uid)

    audit(
        db,
        event_type="mission_control.reset",
        actor="aethos",
        user_id=uid,
        message="Mission Control reset",
        metadata={
            "assignments_cleared": assignments_cleared,
            "jobs_dismissed": jobs_dismissed,
            "reports_cleared": reports_cleared,
            "custom_agents_changed": custom_agents_changed,
            "hard_delete": do_hard and allow_hard,
        },
    )
    return {
        "ok": True,
        "assignments_cleared": assignments_cleared,
        "jobs_dismissed": jobs_dismissed,
        "reports_cleared": reports_cleared,
        "custom_agents_changed": custom_agents_changed,
    }
