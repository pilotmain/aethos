# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentHeartbeat, AgentJob
from app.services.agent_catalog import AGENTS
from app.services.agent_run_service import format_time_ago

_TERMINAL = {"completed", "failed", "cancelled", "rejected", "blocked"}

_STATUS_LIST: tuple[str, str] = (
    ("reset", "aethos"),
    ("dev", "developer"),
    ("qa", "qa"),
    ("ops", "ops"),
    ("strategy", "strategy"),
    ("marketing", "marketing"),
    ("research", "research"),
)


def _line_for_developer(db: Session, app_user_id: str) -> str:
    st = (
        select(AgentJob)
        .where(AgentJob.user_id == app_user_id, AgentJob.worker_type == "dev_executor")
        .order_by(AgentJob.id.desc())
        .limit(8)
    )
    for job in db.scalars(st).all():
        stt = (job.status or "") or ""
        if stt and stt not in _TERMINAL:
            return f"running / latest in-flight — job #{job.id} ({stt})"
    h = (
        db.scalars(
            select(AgentHeartbeat).where(
                AgentHeartbeat.user_id == app_user_id,
                AgentHeartbeat.agent_key == "developer",
            )
        )
        .first()
    )
    if h and (h.current_run_id or h.message):
        m = h.message or ""
        m = f" — {m[:120]}" if m else ""
        return f"worker context — {h.status or 'active'}{m}, last {format_time_ago(h.last_seen_at)}"
    lj = (
        db.scalars(
            select(AgentJob)
            .where(AgentJob.user_id == app_user_id, AgentJob.worker_type == "dev_executor")
            .order_by(AgentJob.id.desc())
            .limit(1)
        )
        .first()
    )
    if lj:
        return f"idle — last dev job #{lj.id} ({lj.status or '—'})"
    return "idle — ask Nexa to run a development task or improve this code."


def _line_for_ops() -> str:
    from app.services.worker_heartbeat import read_heartbeat

    h = read_heartbeat()
    if h and (h.get("status") == "alive" or h.get("last_seen")):
        return "worker alive (see /dev health for detail)"
    return "worker status unknown (no local heartbeat on file; run the host dev executor or `/dev health`)"


def _line_for_heartbeat(db: Session, app_user_id: str, agent_key: str) -> str:
    h = (
        db.scalars(
            select(AgentHeartbeat).where(
                AgentHeartbeat.user_id == app_user_id, AgentHeartbeat.agent_key == agent_key
            )
        )
        .first()
    )
    st = h.status or "idle" if h else "idle"
    seen = format_time_ago(h.last_seen_at) if h else "—"
    if st in ("running",) and h and h.current_run_id:
        return f"{st}, run #{h.current_run_id} — {seen}"
    return f"idle, last {seen}"


def format_agents_status(
    db: Session, app_user_id: str, *, active_topic: str | None = None
) -> str:
    from app.models.conversation_context import ConversationContext

    topic = (active_topic or "").strip()[:200]
    if not topic:
        cctx = db.scalars(
            select(ConversationContext)
            .where(ConversationContext.user_id == str(app_user_id))
            .limit(1)
        ).first()
        if cctx and (cctx.active_topic or "").strip():
            topic = (cctx.active_topic or "")[:200]

    out: list[str] = ["Nexa agent status:", ""]

    for cat_key, hb_key in _STATUS_LIST:
        meta = AGENTS.get(cat_key) or {}
        em = str(meta.get("emoji") or "•")
        name = str(meta.get("display_name") or cat_key)
        if cat_key == "dev":
            sub = _line_for_developer(db, app_user_id)
        elif cat_key == "ops":
            sub = _line_for_ops()
        elif cat_key == "strategy" and topic:
            sub = f"active topic: {topic}"
        else:
            sub = _line_for_heartbeat(db, app_user_id, hb_key)
        out.append(f"{em} {name} — {sub}")
    return "\n".join(out) + f"\n\n_UTC {datetime.utcnow().isoformat()}_"
