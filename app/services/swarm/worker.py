"""
Deterministic assignment worker for developer testing — completes queued spawn work without LLM.

V1 produces stub outputs so orchestration lifecycle (queued → running → completed, dependency unlock)
is observable in Mission Control.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_team import AgentAssignment
from app.services.custom_agents import normalize_agent_key

logger = logging.getLogger(__name__)

_TERMINAL = frozenset({"completed", "failed", "cancelled"})


def _spawn_group_id(row: AgentAssignment) -> str:
    ij = row.input_json if isinstance(row.input_json, dict) else {}
    return str(ij.get("spawn_group_id") or "").strip()


def _depends_on(row: AgentAssignment) -> list[str]:
    ij = row.input_json if isinstance(row.input_json, dict) else {}
    raw = ij.get("depends_on") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        k = normalize_agent_key(str(x))
        if k and k not in out:
            out.append(k)
    return out


def _sibling_completed_for_dep(
    db: Session,
    *,
    user_id: str,
    spawn_group_id: str,
    dep_handle: str,
) -> bool:
    if not spawn_group_id:
        return False
    uid = (user_id or "").strip()[:64]
    hk = normalize_agent_key(dep_handle)
    rows = list(
        db.scalars(
            select(AgentAssignment)
            .where(AgentAssignment.user_id == uid)
            .where(AgentAssignment.status == "completed")
            .order_by(AgentAssignment.id.asc())
        ).all()
    )
    for r in rows:
        if normalize_agent_key(r.assigned_to_handle) != hk:
            continue
        ij = r.input_json if isinstance(r.input_json, dict) else {}
        if str(ij.get("spawn_group_id") or "").strip() == spawn_group_id:
            return True
    return False


def _deps_satisfied(db: Session, *, user_id: str, row: AgentAssignment) -> bool:
    sg = _spawn_group_id(row)
    for dep in _depends_on(row):
        if not _sibling_completed_for_dep(db, user_id=user_id, spawn_group_id=sg, dep_handle=dep):
            return False
    return True


def _stub_output_for_handle(handle: str, task: str) -> dict[str, Any]:
    h = normalize_agent_key(handle)
    tl = (task or "").lower()
    if "researcher" in h or "research" in tl:
        return {
            "kind": "research_notes",
            "artifact": "research_notes",
            "breakthroughs": [
                "Embodied AI manipulation",
                "Autonomous warehouse robotics",
                "Sim-to-real robotics training",
            ],
            "text": "Research summary (deterministic stub).",
        }
    if "analyst" in h or "forecast" in tl:
        return {
            "kind": "forecast",
            "artifact": "forecast",
            "text": (
                "Paragraph 1 — baseline outlook.\n\n"
                "Paragraph 2 — drivers and uncertainties.\n\n"
                "Paragraph 3 — scenarios (deterministic stub)."
            ),
        }
    if h == "qa" or "review" in tl or "risk" in tl:
        return {
            "kind": "qa_report",
            "artifact": "qa_report",
            "text": "Risks and gaps (deterministic stub): coverage, assumptions, verification.",
        }
    return {
        "kind": "assignment_output",
        "artifact": "output",
        "text": f"Completed task (deterministic stub): {(task or '')[:400]}",
    }


def _unlock_waiting_workers(db: Session, *, user_id: str, spawn_group_id: str) -> int:
    """Promote waiting_worker → queued when all depends_on handles are completed in this spawn."""
    if not spawn_group_id:
        return 0
    uid = (user_id or "").strip()[:64]
    pending = list(
        db.scalars(
            select(AgentAssignment)
            .where(AgentAssignment.user_id == uid)
            .where(AgentAssignment.status == "waiting_worker")
        ).all()
    )
    n = 0
    for row in pending:
        ij = row.input_json if isinstance(row.input_json, dict) else {}
        if str(ij.get("spawn_group_id") or "").strip() != spawn_group_id:
            continue
        if _deps_satisfied(db, user_id=uid, row=row):
            row.status = "queued"
            row.error = None
            db.add(row)
            n += 1
    if n:
        db.commit()
    return n


def run_worker_once(db: Session, *, user_id: str, limit: int = 10) -> dict[str, Any]:
    """
    Process up to ``limit`` queued assignments whose dependency handles are satisfied.
    Returns counts and last assignment id touched.
    """
    uid = (user_id or "").strip()[:64]
    processed = 0
    last_id: int | None = None
    errors: list[str] = []

    for _ in range(max(1, limit)):
        candidates = list(
            db.scalars(
                select(AgentAssignment)
                .where(AgentAssignment.user_id == uid)
                .where(AgentAssignment.status == "queued")
                .order_by(AgentAssignment.id.asc())
            ).all()
        )
        picked: AgentAssignment | None = None
        for row in candidates:
            ij0 = row.input_json if isinstance(row.input_json, dict) else {}
            if ij0.get("kind") == "spawn_parent":
                continue
            if _deps_satisfied(db, user_id=uid, row=row):
                picked = row
                break
        if picked is None:
            break

        row = picked
        sg = _spawn_group_id(row)
        row.status = "running"
        db.add(row)
        db.commit()
        db.refresh(row)

        ij = row.input_json if isinstance(row.input_json, dict) else {}
        task = str(ij.get("task") or row.description or "")[:12_000]
        out = _stub_output_for_handle(row.assigned_to_handle, task)
        row.status = "completed"
        row.completed_at = datetime.utcnow()
        row.output_json = out
        row.error = None
        db.add(row)
        db.commit()
        processed += 1
        last_id = row.id

        if sg:
            _unlock_waiting_workers(db, user_id=uid, spawn_group_id=sg)

    return {
        "ok": True,
        "processed": processed,
        "last_assignment_id": last_id,
        "errors": errors,
    }


def run_mission_workers_until_idle(
    db: Session,
    *,
    user_id: str,
    max_iterations: int = 12,
) -> dict[str, Any]:
    """Run ``run_worker_once`` until no queued work remains or iteration budget exhausted."""
    total = 0
    iterations = 0
    while iterations < max_iterations:
        iterations += 1
        snap = run_worker_once(db, user_id=user_id, limit=20)
        n = int(snap.get("processed") or 0)
        total += n
        if n == 0:
            break
    return {"ok": True, "total_processed": total, "iterations": iterations}
