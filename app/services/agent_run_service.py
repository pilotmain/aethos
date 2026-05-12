# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentJob, AgentRun
from app.services import agent_heartbeat_service


def create_run_for_dev_job(
    db: Session, *, app_user_id: str, job: AgentJob, input_text: str
) -> AgentRun:
    jstatus = (job.status or "").lower()
    if jstatus == "blocked":
        run_status = "failed"
    elif jstatus in ("needs_approval", "needs_risk_approval"):
        run_status = "waiting_approval"
    else:
        run_status = "executing"
    run = AgentRun(
        user_id=app_user_id,
        agent_key="developer",
        input_text=(input_text or "")[:50_000],
        status=run_status,
        plan_json={
            "kind": "dev_loop",
            "agent_job_id": job.id,
        },
        related_agent_job_id=job.id,
        result=None,
        error_message=job.error_message,
        approval_required=bool(getattr(job, "approval_required", False)),
    )
    db.add(run)
    db.flush()

    h_msg = f"dev job #{job.id} — {jstatus or '…'}"
    if jstatus == "blocked":
        agent_heartbeat_service.beat(
            db,
            user_id=app_user_id,
            agent_key="developer",
            status="blocked",
            current_run_id=run.id,
            message=(job.error_message or "blocked")[:2000],
        )
    else:
        agent_heartbeat_service.beat(
            db,
            user_id=app_user_id,
            agent_key="developer",
            status="running",
            current_run_id=run.id,
            message=h_msg,
        )
    return run


def get_active_agent_runs(
    db: Session, app_user_id: str, agent_keys: list[str] | None = None
) -> list[AgentRun]:
    st = select(AgentRun).where(AgentRun.user_id == app_user_id)
    if agent_keys:
        st = st.where(AgentRun.agent_key.in_(agent_keys))
    st = st.order_by(AgentRun.id.desc()).limit(50)
    return list(db.scalars(st).all())


def format_time_ago(dt: datetime | None) -> str:
    if not dt:
        return "—"
    delta = datetime.utcnow() - dt
    sec = int(max(0, delta.total_seconds()))
    if sec < 60:
        return f"{max(1, sec)}s ago"
    if sec < 3600:
        return f"{sec // 60}m ago"
    return f"{sec // 3600}h ago"
