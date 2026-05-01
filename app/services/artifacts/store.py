"""DB-backed artifact store — mission-scoped outputs for agent handoff."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.nexa_next_runtime import NexaArtifact, NexaMission, NexaMissionTask


def write_artifact(db: Session, mission_id: str | None, agent_handle: str, artifact: Any) -> None:
    if mission_id is None:
        return
    row = NexaArtifact(mission_id=mission_id, agent_handle=agent_handle, artifact_json=artifact)
    db.add(row)
    db.commit()


def read_artifacts(db: Session, mission_id: str | None) -> list[dict[str, Any]]:
    if mission_id is None:
        return []
    rows = db.scalars(
        select(NexaArtifact).where(NexaArtifact.mission_id == mission_id).order_by(NexaArtifact.id)
    ).all()
    return [
        {
            "mission_id": r.mission_id,
            "agent": r.agent_handle,
            "artifact": r.artifact_json,
        }
        for r in rows
    ]


def clear_store_for_tests(db: Session) -> None:
    """Remove all Nexa Next runtime rows (tests)."""
    db.execute(delete(NexaArtifact))
    db.execute(delete(NexaMissionTask))
    db.execute(delete(NexaMission))
    db.commit()
