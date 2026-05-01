from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.task_repo import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self) -> None:
        self.repo = TaskRepository()

    def list_tasks(self, db: Session, user_id: str):
        return self.repo.list_for_user(db, user_id)

    def list_today(self, db: Session, user_id: str, today: date):
        return self.repo.list_today(db, user_id, today)

    def get_task(self, db: Session, task_id: int, user_id: str):
        task = self.repo.get_for_user(db, task_id, user_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    def create_task(self, db: Session, user_id: str, payload: TaskCreate):
        return self.repo.create(db, user_id, payload)

    def update_task(self, db: Session, task_id: int, user_id: str, payload: TaskUpdate):
        task = self.get_task(db, task_id, user_id)
        return self.repo.update(db, task, payload)

    def complete_task(self, db: Session, task_id: int, user_id: str):
        task = self.get_task(db, task_id, user_id)
        return self.repo.update(db, task, TaskUpdate(status="done"))

    def snooze_task(self, db: Session, task_id: int, user_id: str, for_date: date | None):
        task = self.get_task(db, task_id, user_id)
        return self.repo.update(db, task, TaskUpdate(status="snoozed", suggested_for_date=for_date))

    def delete_task(self, db: Session, task_id: int, user_id: str):
        task = self.get_task(db, task_id, user_id)
        self.repo.delete(db, task)
