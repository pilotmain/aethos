# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""CRUD + APScheduler registration for :class:`~app.models.nexa_scheduler_job.NexaSchedulerJob`."""

from __future__ import annotations

import uuid
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.core.scheduler import scheduler
from app.models.nexa_scheduler_job import NexaSchedulerJob
from app.services.scheduler.worker import execute_scheduled_job


def register_apscheduler_jobs_from_db(db: Session) -> int:
    """Load enabled rows and register ``nexa_sched_{id}`` jobs; returns count."""
    from sqlalchemy import select

    n = 0
    rows = list(db.scalars(select(NexaSchedulerJob).where(NexaSchedulerJob.enabled.is_(True))))
    for row in rows:
        job_id = f"nexa_sched_{row.id}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        if row.kind == "interval" and row.interval_seconds and row.interval_seconds > 0:
            scheduler.add_job(
                execute_scheduled_job,
                IntervalTrigger(seconds=int(row.interval_seconds)),
                id=job_id,
                args=[row.id],
                replace_existing=True,
            )
            n += 1
        elif row.kind == "cron" and (row.cron_expression or "").strip():
            expr = str(row.cron_expression).strip()
            scheduler.add_job(
                execute_scheduled_job,
                CronTrigger.from_crontab(expr),
                id=job_id,
                args=[row.id],
                replace_existing=True,
            )
            n += 1
    return n


class NexaSchedulerService:
    def list_jobs(self, db: Session, user_id: str) -> list[dict[str, Any]]:
        from sqlalchemy import select

        rows = list(
            db.scalars(
                select(NexaSchedulerJob)
                .where(NexaSchedulerJob.user_id == user_id)
                .order_by(NexaSchedulerJob.created_at.desc())
            )
        )
        return [
            {
                "id": r.id,
                "label": r.label,
                "mission_text": r.mission_text,
                "kind": r.kind,
                "interval_seconds": r.interval_seconds,
                "cron_expression": r.cron_expression,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def create_job(
        self,
        db: Session,
        *,
        user_id: str,
        mission_text: str,
        kind: str,
        interval_seconds: int | None = None,
        cron_expression: str | None = None,
        label: str = "",
    ) -> NexaSchedulerJob:
        jid = str(uuid.uuid4())
        row = NexaSchedulerJob(
            id=jid,
            user_id=user_id,
            label=(label or "")[:512],
            mission_text=mission_text.strip(),
            kind=kind if kind in ("interval", "cron") else "interval",
            interval_seconds=interval_seconds,
            cron_expression=(cron_expression or "").strip() or None,
            enabled=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        register_apscheduler_jobs_from_db(db)
        return row

    def delete_job(self, db: Session, *, user_id: str, job_id: str) -> bool:
        row = db.get(NexaSchedulerJob, job_id)
        if row is None or row.user_id != user_id:
            return False
        db.delete(row)
        db.commit()
        try:
            scheduler.remove_job(f"nexa_sched_{job_id}")
        except Exception:
            pass
        register_apscheduler_jobs_from_db(db)
        return True


__all__ = ["NexaSchedulerService", "register_apscheduler_jobs_from_db"]
