# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.core.db import SessionLocal
from app.repositories.checkin_repo import CheckInRepository
from app.services.checkin_service import CheckInService
from app.services.task_service import TaskService
from app.schemas.task import TaskCreate


def test_schedule_for_tasks_skips_duplicate_title_prompts() -> None:
    db = SessionLocal()
    tasks = TaskService()
    checkins = CheckInService()
    user_id = "checkin_dedupe_user"
    try:
        first = tasks.create_task(db, user_id, TaskCreate(title="Finish report", priority_score=50))
        second = tasks.create_task(db, user_id, TaskCreate(title="Finish report", priority_score=50))

        checkins.schedule_for_tasks(db, user_id, [first], planning_style="gentle")
        checkins.schedule_for_tasks(db, user_id, [second], planning_style="gentle")

        pending = CheckInRepository().list_pending(db, user_id)
        assert len(pending) == 1
    finally:
        db.close()
