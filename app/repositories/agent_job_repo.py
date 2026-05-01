import logging
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models.agent_job import AgentJob

logger = logging.getLogger(__name__)


class AgentJobRepository:
    def create(self, db: Session, **kwargs) -> AgentJob:
        job = AgentJob(**kwargs)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def get(self, db: Session, job_id: int, user_id: str | None = None) -> AgentJob | None:
        stmt = select(AgentJob).where(AgentJob.id == job_id)
        if user_id is not None:
            stmt = stmt.where(AgentJob.user_id == user_id)
        return db.scalars(stmt).first()

    def get_latest_by_statuses_for_user(
        self, db: Session, user_id: str, statuses: list[str]
    ) -> AgentJob | None:
        if not statuses:
            return None
        stmt = (
            select(AgentJob)
            .where(AgentJob.user_id == user_id)
            .where(AgentJob.status.in_(statuses))
            .order_by(AgentJob.updated_at.desc(), AgentJob.created_at.desc())
            .limit(1)
        )
        return db.scalars(stmt).first()

    def list_for_user(self, db: Session, user_id: str, limit: int = 20) -> list[AgentJob]:
        stmt = (
            select(AgentJob)
            .where(AgentJob.user_id == user_id)
            .order_by(AgentJob.created_at.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    def list_by_status(self, db: Session, status: str, worker_type: str | None = None) -> list[AgentJob]:
        stmt = select(AgentJob).where(AgentJob.status == status)
        if worker_type is not None:
            stmt = stmt.where(AgentJob.worker_type == worker_type)
        stmt = stmt.order_by(AgentJob.updated_at.asc(), AgentJob.created_at.asc())
        return list(db.scalars(stmt).all())

    def list_recent(self, db: Session, limit: int = 100) -> list[AgentJob]:
        stmt = select(AgentJob).order_by(AgentJob.updated_at.desc(), AgentJob.created_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    def get_latest_actionable(self, db: Session, user_id: str) -> AgentJob | None:
        stmt = (
            select(AgentJob)
            .where(AgentJob.user_id == user_id)
            .where(
                AgentJob.status.in_(
                    [
                        "queued",
                        "needs_approval",
                        "approved",
                        "in_progress",
                        "agent_running",
                        "changes_ready",
                        "waiting_approval",
                        "waiting_for_cursor",
                        "approved_to_commit",
                        "needs_risk_approval",
                    ]
                )
            )
            .order_by(AgentJob.created_at.desc())
            .limit(1)
        )
        return db.scalars(stmt).first()

    def get_next_for_worker(self, db: Session, worker_type: str) -> AgentJob | None:
        # Pick the worker queue by *worker_type* (e.g. dev_executor, local_tool) — not by *kind*
        # (e.g. dev_task). kind describes the job class; worker_type is who should run it.
        stmt = (
            select(AgentJob)
            .where(AgentJob.worker_type == worker_type)
            .where(AgentJob.status.in_(["queued", "approved"]))
            .order_by(AgentJob.created_at.asc())
            .limit(1)
        )
        job = db.scalars(stmt).first()
        logger.debug(
            "get_next_for_worker worker_type=%s found id=%s status=%s kind=%s",
            worker_type,
            job.id if job else None,
            (job.status if job else None),
            (job.kind if job else None),
        )
        return job

    def get_next_for_worker_statuses(
        self, db: Session, worker_type: str, statuses: list[str]
    ) -> AgentJob | None:
        stmt = (
            select(AgentJob)
            .where(AgentJob.worker_type == worker_type)
            .where(AgentJob.status.in_(statuses))
            .order_by(AgentJob.created_at.asc())
            .limit(1)
        )
        job = db.scalars(stmt).first()
        logger.debug(
            "get_next_for_worker_statuses worker_type=%s statuses=%s found id=%s status=%s kind=%s",
            worker_type,
            statuses,
            job.id if job else None,
            (job.status if job else None),
            (job.kind if job else None),
        )
        return job

    def get_latest_in_progress_for_worker(self, db: Session, worker_type: str) -> AgentJob | None:
        stmt = (
            select(AgentJob)
            .where(AgentJob.worker_type == worker_type)
            .where(AgentJob.status.in_(["in_progress", "waiting_for_cursor"]))
            .order_by(AgentJob.updated_at.desc())
            .limit(1)
        )
        return db.scalars(stmt).first()

    def has_dev_executor_runnable(self, db: Session) -> bool:
        """Any work the dev_agent_executor script can process in one pass."""
        pending = (
            "review_approved",
            "commit_approved",
            "approved",
            "waiting_for_cursor",
            "approved_to_commit",
        )
        stmt = (
            select(AgentJob.id)
            .where(AgentJob.worker_type == "dev_executor")
            .where(AgentJob.status.in_(pending))
            .limit(1)
        )
        return db.scalars(stmt).first() is not None

    def update(self, db: Session, job: AgentJob, **changes) -> AgentJob:
        for key, value in changes.items():
            setattr(job, key, value)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def mark_started(self, db: Session, job: AgentJob) -> AgentJob:
        return self.update(db, job, status="in_progress", started_at=datetime.utcnow(), error_message=None)

    def acquire_job_lock(
        self, db: Session, job: AgentJob, worker_id: str, ttl_seconds: int = 1800
    ) -> bool:
        now = datetime.utcnow()
        expires = now + timedelta(seconds=ttl_seconds)
        j = db.get(AgentJob, job.id)
        if not j:
            return False
        if (
            (j.locked_by or "") == worker_id
            and j.lock_expires_at
            and j.lock_expires_at > now
        ):
            r = db.execute(
                update(AgentJob)
                .where(AgentJob.id == job.id)
                .where(AgentJob.locked_by == worker_id)
                .values(locked_at=now, lock_expires_at=expires)
            )
            db.commit()
            return (r.rowcount or 0) > 0
        r2 = db.execute(
            update(AgentJob)
            .where(AgentJob.id == job.id)
            .where(
                or_(
                    AgentJob.lock_expires_at.is_(None),
                    AgentJob.lock_expires_at < now,
                )
            )
            .values(locked_by=worker_id, locked_at=now, lock_expires_at=expires)
        )
        db.commit()
        return (r2.rowcount or 0) > 0

    def release_job_lock(self, db: Session, job: AgentJob) -> AgentJob:
        return self.update(
            db,
            job,
            locked_by=None,
            locked_at=None,
            lock_expires_at=None,
        )

    def count_matching(
        self, db: Session, *, worker_type: str, statuses: list[str]
    ) -> int:
        if not statuses:
            return 0
        stmt = (
            select(func.count())
            .select_from(AgentJob)
            .where(AgentJob.worker_type == worker_type)
            .where(AgentJob.status.in_(statuses))
        )
        return int(db.scalar(stmt) or 0)

    def count_dev_executor_in_statuses(
        self, db: Session, statuses: list[str]
    ) -> int:
        if not statuses:
            return 0
        stmt = (
            select(func.count())
            .select_from(AgentJob)
            .where(AgentJob.worker_type == "dev_executor")
            .where(AgentJob.status.in_(statuses))
        )
        return int(db.scalar(stmt) or 0)
