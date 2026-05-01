from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentHeartbeat


def beat(
    db: Session,
    *,
    user_id: str,
    agent_key: str,
    status: str,
    current_run_id: int | None = None,
    message: str | None = None,
) -> AgentHeartbeat:
    st = select(AgentHeartbeat).where(
        AgentHeartbeat.user_id == user_id, AgentHeartbeat.agent_key == agent_key
    )
    hb = db.scalars(st).first()
    if not hb:
        hb = AgentHeartbeat(user_id=user_id, agent_key=agent_key)
        db.add(hb)
    hb.status = status
    hb.current_run_id = current_run_id
    hb.message = message
    hb.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(hb)
    return hb
