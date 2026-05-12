# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Delete aged Nexa Next runtime rows (artifacts, missions, audit calls)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.nexa_next_runtime import NexaArtifact, NexaExternalCall, NexaMission, NexaMissionTask
from app.services.events.bus import EVENTS


def trim_in_memory_event_bus(max_keep: int = 2000) -> int:
    """Drop oldest bus entries when over capacity (events lack timestamps)."""
    removed = 0
    while len(EVENTS) > max_keep:
        EVENTS.popleft()
        removed += 1
    return removed


def run_retention_cleanup(db: Session) -> dict[str, int]:
    """
    Remove missions (and dependent tasks/artifacts) older than configured retention.

    ``NEXA_DATA_RETENTION_DAYS <= 0`` skips deletion.
    """
    days = get_settings().nexa_data_retention_days
    out: dict[str, int] = {"missions_deleted": 0, "external_calls_deleted": 0, "events_trimmed": 0}
    if days <= 0:
        out["skipped"] = 1
        return out

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    mids = list(
        db.scalars(select(NexaMission.id).where(NexaMission.created_at < cutoff)).all()
    )
    if not mids:
        out["events_trimmed"] = trim_in_memory_event_bus()
        return out

    db.execute(delete(NexaArtifact).where(NexaArtifact.mission_id.in_(mids)))
    db.execute(delete(NexaMissionTask).where(NexaMissionTask.mission_id.in_(mids)))
    db.execute(delete(NexaMission).where(NexaMission.id.in_(mids)))
    out["missions_deleted"] = len(mids)

    ec = db.execute(delete(NexaExternalCall).where(NexaExternalCall.created_at < cutoff))
    try:
        out["external_calls_deleted"] = ec.rowcount or 0
    except Exception:
        out["external_calls_deleted"] = 0

    db.commit()

    out["events_trimmed"] = trim_in_memory_event_bus()
    return out


__all__ = ["run_retention_cleanup", "trim_in_memory_event_bus"]
