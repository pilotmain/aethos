# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.checkin_repo import CheckInRepository
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.task_service import TaskService


class CheckInService:
    def __init__(self) -> None:
        self.repo = CheckInRepository()
        self.task_service = TaskService()
        self.memory_service = MemoryService()
        self.llm = LLMService()

    def schedule_for_tasks(self, db: Session, user_id: str, tasks: list, planning_style: str) -> list:
        rows = []
        now = datetime.now(UTC).replace(tzinfo=None)
        existing = self.repo.list_pending(db, user_id)
        existing_prompts = [(row.prompt_text or "").lower() for row in existing]
        for idx, task in enumerate(tasks[:3], start=1):
            title_key = (task.title or "").strip().lower()
            if title_key and any(title_key in prompt for prompt in existing_prompts):
                continue
            prompt = self.llm.generate_followup(task.title, planning_style=planning_style)
            scheduled_for = now + timedelta(hours=2 if idx == 1 else 4 + idx)
            rows.append(self.repo.create(db, user_id=user_id, task_id=task.id, prompt_text=prompt, scheduled_for=scheduled_for))
        return rows

    def list_pending(self, db: Session, user_id: str):
        return self.repo.list_pending(db, user_id)

    def cancel(self, db: Session, user_id: str, checkin_id: int):
        row = self.repo.cancel_for_user(db, user_id, checkin_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")
        return {"status": row.status, "checkin_id": row.id}

    def respond(self, db: Session, user_id: str, checkin_id: int, response_text: str) -> dict:
        row = self.repo.get_for_user(db, checkin_id, user_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")
        lowered = response_text.lower().strip()
        response_type = "custom"
        if any(token in lowered for token in ["done", "finished", "complete"]):
            response_type = "done"
            task = self.task_service.complete_task(db, row.task_id, user_id)
            message = f"Nice. '{task.title}' is marked done."
        elif any(token in lowered for token in ["later", "tomorrow", "snooze", "not yet"]):
            response_type = "snooze"
            target = date.today() + timedelta(days=1)
            task = self.task_service.snooze_task(db, row.task_id, user_id, target)
            micro_step = self.llm.generate_micro_step(task.title)
            message = f"No problem. I moved '{task.title}' to tomorrow. {micro_step}"
        else:
            task = self.task_service.get_task(db, row.task_id, user_id)
            message = self.llm.generate_micro_step(task.title)
        self.repo.respond(db, row, response_text=response_text, response_type=response_type)
        return {"message": message, "response_type": response_type}

    def process_due(self, db: Session) -> list:
        now = datetime.now(UTC).replace(tzinfo=None)
        due = self.repo.list_due_unsent(db, now)
        for row in due:
            self.repo.mark_sent(db, row, now)
        return due
