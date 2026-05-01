from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository:
    def list_for_user(self, db: Session, user_id: str) -> list[Task]:
        stmt = select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())
        return list(db.scalars(stmt).all())

    def list_today(self, db: Session, user_id: str, today: date) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .where(Task.status.in_(["pending", "in_progress", "snoozed"]))
            .where((Task.suggested_for_date == today) | (Task.suggested_for_date.is_(None)))
            .order_by(Task.priority_score.desc(), Task.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    def get_for_user(self, db: Session, task_id: int, user_id: str) -> Task | None:
        return db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))

    def list_open_for_user(self, db: Session, user_id: str) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .where(Task.status.in_(["pending", "in_progress", "snoozed"]))
            .order_by(Task.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    def list_matching_for_user(self, db: Session, user_id: str, query: str) -> list[Task]:
        q = (query or "").strip().lower()
        if not q:
            return []
        rows = self.list_for_user(db, user_id)
        if q.isdigit():
            qid = int(q)
            return [task for task in rows if task.id == qid]
        matches: list[Task] = []
        for task in rows:
            haystacks = [task.title or "", task.description or ""]
            if any(q in value.lower() for value in haystacks if value):
                matches.append(task)
        return matches

    def create(self, db: Session, user_id: str, payload: TaskCreate, brain_dump_id: str | None = None) -> Task:
        task = Task(user_id=user_id, brain_dump_id=brain_dump_id, **payload.model_dump())
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def update(self, db: Session, task: Task, payload: TaskUpdate) -> Task:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def save_many(self, db: Session, tasks: list[Task]) -> list[Task]:
        db.add_all(tasks)
        db.commit()
        for task in tasks:
            db.refresh(task)
        return tasks

    def delete(self, db: Session, task: Task) -> None:
        db.delete(task)
        db.commit()
