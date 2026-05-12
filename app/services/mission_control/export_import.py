# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Export / import Nexa Next mission bundles (Phase 20)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nexa_next_runtime import NexaArtifact, NexaMission, NexaMissionTask


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def export_mission_bundle(db: Session, *, mission_id: str, user_id: str) -> dict[str, Any]:
    m = db.get(NexaMission, mission_id)
    if m is None or m.user_id != user_id:
        return {}

    tasks = db.scalars(select(NexaMissionTask).where(NexaMissionTask.mission_id == mission_id)).all()
    arts = db.scalars(select(NexaArtifact).where(NexaArtifact.mission_id == mission_id)).all()

    return {
        "version": 1,
        "exported_at": _utc_now().isoformat(),
        "mission": {
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "input_text": m.input_text,
        },
        "tasks": [
            {
                "agent_handle": t.agent_handle,
                "role": t.role,
                "task": t.task,
                "status": t.status,
                "depends_on": t.depends_on or [],
                "output_json": t.output_json,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "duration_ms": t.duration_ms,
            }
            for t in tasks
        ],
        "artifacts": [
            {
                "agent_handle": a.agent_handle,
                "artifact_json": a.artifact_json,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in arts
        ],
    }


def import_mission_bundle(db: Session, *, user_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    """Create a new mission from an export bundle (new ids)."""
    raw_m = bundle.get("mission") if isinstance(bundle.get("mission"), dict) else {}
    title = str(raw_m.get("title") or "Imported mission")[:2000]
    input_text = raw_m.get("input_text")
    if input_text is not None:
        input_text = str(input_text)[:50000]

    new_mid = str(uuid.uuid4())
    db.add(
        NexaMission(
            id=new_mid,
            user_id=user_id,
            title=title,
            status=str(raw_m.get("status") or "running")[:32],
            input_text=input_text,
        )
    )

    tasks_in = bundle.get("tasks") if isinstance(bundle.get("tasks"), list) else []
    for t in tasks_in:
        if not isinstance(t, dict):
            continue
        db.add(
            NexaMissionTask(
                mission_id=new_mid,
                agent_handle=str(t.get("agent_handle") or "agent")[:128],
                role=str(t.get("role") or "")[:512],
                task=str(t.get("task") or ""),
                status=str(t.get("status") or "queued")[:32],
                depends_on=list(t.get("depends_on") or []),
                output_json=t.get("output_json"),
            )
        )

    arts_in = bundle.get("artifacts") if isinstance(bundle.get("artifacts"), list) else []
    for a in arts_in:
        if not isinstance(a, dict):
            continue
        db.add(
            NexaArtifact(
                mission_id=new_mid,
                agent_handle=str(a.get("agent_handle") or "agent")[:128],
                artifact_json=a.get("artifact_json"),
            )
        )

    db.commit()
    return {"mission_id": new_mid, "tasks_imported": len(tasks_in), "artifacts_imported": len(arts_in)}
