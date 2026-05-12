# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""APScheduler (asyncio) driver for Phase 13 cron jobs."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import REPO_ROOT, get_settings
from app.services.cron.executor import JobExecutor
from app.services.cron.job_store import CronJobStore
from app.services.cron.models import CronJob, JobActionType, JobStatus

logger = logging.getLogger("nexa.cron.scheduler")


def _sqlite_path_from_url(url: str) -> Path:
    raw = (url or "").strip()
    if raw.startswith("sqlite:///"):
        rest = raw[len("sqlite:///") :].lstrip("/")
        p = Path(rest)
        if not p.is_absolute():
            return (REPO_ROOT / rest).resolve()
        return p.resolve()
    return (REPO_ROOT / "data" / "nexa_cron_jobs.sqlite").resolve()


def _zoneinfo(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


class NexaCronScheduler:
    """Singleton AsyncIOScheduler + SQLite metadata store."""

    _instance: NexaCronScheduler | None = None

    def __new__(cls) -> NexaCronScheduler:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._scheduler: AsyncIOScheduler | None = None
        self._store: CronJobStore | None = None
        self._executor = JobExecutor()
        self._initialized = True

    def _ensure_store(self) -> CronJobStore:
        if self._store is None:
            s = get_settings()
            path = _sqlite_path_from_url(getattr(s, "nexa_cron_job_store", "") or "")
            self._store = CronJobStore(path)
        return self._store

    def start(self) -> None:
        """Bind AsyncIOScheduler to the running event loop and load jobs."""
        s = get_settings()
        if not getattr(s, "nexa_cron_enabled", True):
            logger.info("NEXA_CRON_ENABLED=false — cron scheduler not started")
            return
        if self._scheduler is not None and self._scheduler.running:
            return

        tz = _zoneinfo(str(getattr(s, "nexa_cron_default_timezone", None) or "UTC"))
        self._scheduler = AsyncIOScheduler(jobstores={"default": MemoryJobStore()}, timezone=tz)
        store = self._ensure_store()
        for job in store.list_all(status=JobStatus.ACTIVE):
            self._add_apscheduler_job(job, store)

        self._scheduler.start()
        logger.info("Nexa cron scheduler started jobs=%s", len(store.list_all()))

    def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Nexa cron scheduler stopped")

    def _add_apscheduler_job(self, job: CronJob, store: CronJobStore) -> None:
        if not self._scheduler:
            return
        tz = _zoneinfo(job.timezone or get_settings().nexa_cron_default_timezone or "UTC")
        trigger = CronTrigger.from_crontab(job.cron_expression, timezone=tz)
        self._scheduler.add_job(
            self._executor.execute_job_by_id,
            trigger=trigger,
            kwargs={"job_id": job.id, "store": store},
            id=job.id,
            name=job.name,
            replace_existing=True,
            misfire_grace_time=300,
            max_instances=1,
            coalesce=True,
        )
        try:
            now = datetime.now(tz)
            nxt = trigger.get_next_fire_time(None, now)
            if nxt:
                store.update_next_run(job.id, nxt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cron next_run compute failed id=%s err=%s", job.id, exc)

    def add_job(
        self,
        *,
        name: str,
        cron_expression: str,
        action_type: JobActionType,
        action_payload: dict[str, Any],
        created_by: str | None = None,
        created_by_channel: str | None = None,
        timezone: str | None = None,
    ) -> CronJob:
        store = self._ensure_store()
        tz_name = (timezone or get_settings().nexa_cron_default_timezone or "UTC").strip()
        CronTrigger.from_crontab(cron_expression, timezone=_zoneinfo(tz_name))
        jid = uuid.uuid4().hex[:12]
        job = CronJob(
            id=jid,
            name=name[:512],
            cron_expression=cron_expression.strip(),
            action_type=action_type,
            action_payload=action_payload,
            status=JobStatus.ACTIVE,
            created_by=created_by,
            created_by_channel=created_by_channel,
            timezone=tz_name,
        )
        store.save(job)
        if self._scheduler and self._scheduler.running:
            self._add_apscheduler_job(job, store)
        logger.info("cron job registered id=%s expr=%s", job.id, job.cron_expression)
        return job

    def remove_job(self, job_id: str) -> bool:
        store = self._ensure_store()
        if self._scheduler:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:  # noqa: BLE001
                pass
        return store.delete(job_id)

    def pause_job(self, job_id: str) -> bool:
        store = self._ensure_store()
        job = store.get(job_id)
        if not job:
            return False
        job.status = JobStatus.PAUSED
        store.save(job)
        if self._scheduler:
            try:
                self._scheduler.pause_job(job_id)
            except Exception:  # noqa: BLE001
                pass
        return True

    def resume_job(self, job_id: str) -> bool:
        store = self._ensure_store()
        job = store.get(job_id)
        if not job:
            return False
        job.status = JobStatus.ACTIVE
        store.save(job)
        if self._scheduler and self._scheduler.running:
            try:
                self._scheduler.resume_job(job_id)
            except Exception:  # noqa: BLE001
                try:
                    self._scheduler.remove_job(job_id)
                except Exception:  # noqa: BLE001
                    pass
                self._add_apscheduler_job(job, store)
        return True

    def list_jobs(self) -> list[CronJob]:
        return self._ensure_store().list_all()


def get_nexa_cron_scheduler() -> NexaCronScheduler:
    return NexaCronScheduler()


__all__ = ["NexaCronScheduler", "get_nexa_cron_scheduler", "_sqlite_path_from_url"]
