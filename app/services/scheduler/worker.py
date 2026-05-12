# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execute a stored scheduler job through :class:`~app.services.gateway.runtime.NexaGateway`."""

from __future__ import annotations

from app.core.db import SessionLocal
from app.models.nexa_scheduler_job import NexaSchedulerJob
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.logging.logger import get_logger
from app.services.scheduler.dev_jobs import execute_dev_mission_job

_log = get_logger("scheduler.worker")


def execute_scheduled_job(job_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(NexaSchedulerJob, job_id)
        if row is None:
            _log.warning("scheduler job missing id=%s", job_id)
            return
        if not row.enabled:
            return
        try:
            if execute_dev_mission_job(db, row):
                return
        except Exception:
            _log.exception("dev_mission scheduler job failed id=%s", job_id)
            return
        text = (row.mission_text or "").strip()
        if not text:
            return
        uid = (row.user_id or "").strip()
        if not uid:
            return
        try:
            gctx = GatewayContext.from_channel(uid, "scheduler", {"via_gateway": True})
            NexaGateway().handle_message(gctx, text, db=db)
        except Exception:
            _log.exception("scheduler job failed id=%s", job_id)


__all__ = ["execute_scheduled_job"]
