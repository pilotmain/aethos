from app.core.db import SessionLocal
from app.repositories.checkin_repo import CheckInRepository
from app.services.checkin_service import CheckInService
from app.services.memory_service import MemoryService
from app.services.task_service import TaskService
from app.schemas.task import TaskCreate


def test_memory_remember_and_forget_also_clears_matching_tasks() -> None:
    service = MemoryService()
    tasks = TaskService()
    db = SessionLocal()
    user_id = "memory_test_user"
    try:
        service.remember_note(db, user_id, "Report for April is no longer needed", category="user_note")
        tasks.create_task(db, user_id, TaskCreate(title="Finish report", priority_score=50))

        result = service.forget(db, user_id, "report")
        remaining = tasks.list_tasks(db, user_id)

        assert result.deleted_notes >= 1
        assert result.deleted_tasks >= 1
        assert all("report" not in task.title.lower() for task in remaining)
    finally:
        db.close()


def test_forget_returns_matching_task_and_checkin_ids() -> None:
    service = MemoryService()
    tasks = TaskService()
    checkins = CheckInService()
    db = SessionLocal()
    user_id = "memory_test_user_ids"
    try:
        task = tasks.create_task(db, user_id, TaskCreate(title="Finish report", priority_score=50))
        checkins.schedule_for_tasks(db, user_id, [task], planning_style="gentle")

        result = service.forget(db, user_id, "report")
        pending = CheckInRepository().list_pending(db, user_id)

        assert result.deleted_task_ids
        assert task.id in result.deleted_task_ids
        assert result.cancelled_checkin_ids
        assert pending == []
    finally:
        db.close()
