# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Remove persisted Agent Graph rows whose handle is a URL scheme (``http``/``https``), not a real agent."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.nexa_next_runtime import NexaArtifact, NexaMission, NexaMissionTask


def purge_scheme_impostor_tasks(db: Session) -> dict[str, int]:
    """
    Delete tasks whose ``agent_handle`` is ``http`` or ``https`` (paste / parser artifacts).

    Then remove missions that have no remaining tasks and their artifacts.
    """
    r = db.execute(
        delete(NexaMissionTask).where(func.lower(NexaMissionTask.agent_handle).in_(["http", "https"]))
    )
    n_tasks = int(r.rowcount or 0)

    all_mids = {x for x in db.scalars(select(NexaMission.id)).all()}
    covered = {x for x in db.scalars(select(NexaMissionTask.mission_id).distinct()).all()}
    orphan_ids = list(all_mids - covered)
    n_art = 0
    n_mis = 0
    if orphan_ids:
        ar = db.execute(delete(NexaArtifact).where(NexaArtifact.mission_id.in_(orphan_ids)))
        n_art = int(ar.rowcount or 0)
        mr = db.execute(delete(NexaMission).where(NexaMission.id.in_(orphan_ids)))
        n_mis = int(mr.rowcount or 0)
    db.flush()
    return {"tasks_deleted": n_tasks, "missions_deleted": n_mis, "artifacts_deleted": n_art}


__all__ = ["purge_scheme_impostor_tasks"]
