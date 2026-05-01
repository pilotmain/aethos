"""Nexa Gateway runtime — single entry for channels → missions → agents → MC."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NexaGateway:
    """
    Central gateway: owns admission for web, Telegram, and future channels.

    Channels must call ``handle_message`` rather than invoking agents/tools directly.
    """

    def handle_message(
        self,
        text: str,
        user_id: str,
        *,
        db: Session | None = None,
        channel: str = "web",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = channel, metadata
        from app.core.db import SessionLocal
        from app.services.missions.parser import parse_mission

        mission = parse_mission(text)

        if not mission:
            return {"mode": "chat", "text": "No mission detected"}

        if db is not None:
            return self._run_mission(mission, user_id, db)

        with SessionLocal() as session:
            return self._run_mission(mission, user_id, session)

    def _run_mission(self, mission: dict[str, Any], user_id: str, db: Session) -> dict[str, Any]:
        from app.models.nexa_next_runtime import NexaMission, NexaMissionTask
        from app.services.events.bus import publish
        from app.services.mission_control.nexa_next_state import update_state
        from app.services.runtime_agents.factory import create_runtime_agents
        from app.services.workers.loop import run_until_complete

        mission_id = str(uuid.uuid4())
        agents = create_runtime_agents(mission, user_id, mission_id=mission_id)

        title = str(mission.get("title") or "Untitled Mission")[:2000]
        db.add(NexaMission(id=mission_id, user_id=user_id, title=title, status="running"))
        for agent in agents:
            row = NexaMissionTask(
                mission_id=mission_id,
                agent_handle=agent["handle"],
                role=agent["role"],
                task=agent["task"],
                status="queued",
                depends_on=list(agent["depends_on"]),
            )
            db.add(row)
            db.flush()
            agent["task_pk"] = row.id
        db.commit()

        publish({"type": "mission.started", "mission_id": mission_id, "user_id": user_id})

        result = run_until_complete(agents, mission, db)

        nm = db.get(NexaMission, mission_id)
        if nm is not None:
            nm.status = "completed"
            db.commit()

        publish({"type": "mission.completed", "mission_id": mission_id, "user_id": user_id})

        update_state(result)

        return {
            "status": "completed",
            "mission": mission,
            "result": result,
        }
