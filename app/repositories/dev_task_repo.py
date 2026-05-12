# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dev_task import DevTask


class DevTaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: str,
        title: str,
        description: str,
        *,
        source: str = "telegram",
    ) -> DevTask:
        task = DevTask(
            user_id=user_id,
            title=title,
            description=description,
            status="queued",
            source=source,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_next_queued(self) -> DevTask | None:
        return self.db.scalars(
            select(DevTask)
            .where(DevTask.status == "queued")
            .order_by(DevTask.created_at.asc())
            .limit(1)
        ).first()

    def get_latest_in_progress(self) -> DevTask | None:
        return self.db.scalars(
            select(DevTask)
            .where(DevTask.status == "in_progress")
            .order_by(DevTask.updated_at.desc())
            .limit(1)
        ).first()

    def mark_in_progress(self, task: DevTask, branch_name: str) -> None:
        task.status = "in_progress"
        task.branch_name = branch_name
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

    def mark_completed(
        self,
        task: DevTask,
        *,
        commit_sha: str | None = None,
        pr_url: str | None = None,
    ) -> None:
        task.status = "completed"
        if commit_sha is not None:
            task.commit_sha = commit_sha
        if pr_url is not None:
            task.pr_url = pr_url
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

    def mark_failed(self, task: DevTask, error_message: str) -> None:
        task.status = "failed"
        em = (error_message or "")[:4000]
        task.error_message = em if em else "Unknown error"
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
