from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.task import TaskRead


class PlanTaskReason(BaseModel):
    task_id: int
    reason: str | None = None
    display_order: int


class PlanRead(BaseModel):
    id: str
    user_id: str
    plan_date: date
    summary: str
    mode: str
    tasks: list[TaskRead]
    reasons: list[PlanTaskReason]
    created_at: datetime


class GeneratePlanRequest(BaseModel):
    text: str
    input_source: str = "text"


class GeneratePlanResponse(BaseModel):
    plan: PlanRead | None = None
    needs_more_context: bool = False
    detected_state: str
    extracted_tasks_count: int
