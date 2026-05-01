from datetime import date, timedelta

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
service = TaskService()


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.list_tasks(db, user_id)


@router.get("/today", response_model=list[TaskRead])
def list_today(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.list_today(db, user_id, date.today())


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.create_task(db, user_id, payload)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.get_task(db, task_id, user_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.update_task(db, task_id, user_id, payload)


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.complete_task(db, task_id, user_id)


@router.post("/{task_id}/snooze", response_model=TaskRead)
def snooze_task(task_id: int, days: int = 1, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    target = date.today() + timedelta(days=max(1, min(days, 30)))
    return service.snooze_task(db, task_id, user_id, target)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    service.delete_task(db, task_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
