"""SQLite persistence for cron job metadata (Phase 13)."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.cron.models import CronJob, JobActionType, JobStatus

logger = logging.getLogger(__name__)


class CronJobStore:
    """SQLite persistent storage for cron jobs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cron_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    last_error TEXT,
                    run_count INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_by_channel TEXT,
                    timezone TEXT DEFAULT 'UTC'
                )
                """
            )

    def save(self, job: CronJob) -> None:
        job.updated_at = datetime.utcnow()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cron_jobs
                (id, name, cron_expression, action_type, action_payload, status,
                 created_at, updated_at, last_run_at, next_run_at, last_error,
                 run_count, created_by, created_by_channel, timezone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.name,
                    job.cron_expression,
                    job.action_type.value,
                    json.dumps(job.action_payload),
                    job.status.value,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.last_run_at.isoformat() if job.last_run_at else None,
                    job.next_run_at.isoformat() if job.next_run_at else None,
                    job.last_error,
                    job.run_count,
                    job.created_by,
                    job.created_by_channel,
                    job.timezone,
                ),
            )

    def get(self, job_id: str) -> CronJob | None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM cron_jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            return self._row_to_job(row) if row else None

    def list_all(self, status: JobStatus | None = None) -> list[CronJob]:
        with sqlite3.connect(self.db_path) as conn:
            if status:
                cur = conn.execute(
                    "SELECT * FROM cron_jobs WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                )
            else:
                cur = conn.execute("SELECT * FROM cron_jobs ORDER BY created_at DESC")
            return [self._row_to_job(r) for r in cur.fetchall()]

    def delete(self, job_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
            return cur.rowcount > 0

    def update_last_run(self, job_id: str, *, success: bool, error: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            if success:
                conn.execute(
                    """
                    UPDATE cron_jobs
                    SET last_run_at = ?, last_error = NULL, run_count = run_count + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, now, job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE cron_jobs
                    SET last_run_at = ?, last_error = ?, run_count = run_count + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, error or "error", now, job_id),
                )

    def update_next_run(self, job_id: str, next_run_at: datetime) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE cron_jobs SET next_run_at = ?, updated_at = ? WHERE id = ?",
                (next_run_at.isoformat(), now, job_id),
            )

    def _row_to_job(self, row: tuple[Any, ...]) -> CronJob:
        return CronJob(
            id=row[0],
            name=row[1],
            cron_expression=row[2],
            action_type=JobActionType(row[3]),
            action_payload=json.loads(row[4]),
            status=JobStatus(row[5]),
            created_at=datetime.fromisoformat(row[6]),
            updated_at=datetime.fromisoformat(row[7]),
            last_run_at=datetime.fromisoformat(row[8]) if row[8] else None,
            next_run_at=datetime.fromisoformat(row[9]) if row[9] else None,
            last_error=row[10],
            run_count=int(row[11] or 0),
            created_by=row[12],
            created_by_channel=row[13],
            timezone=row[14] or "UTC",
        )


__all__ = ["CronJobStore"]
