from datetime import date, datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str = "general"
    priority_score: int = Field(default=50, ge=1, le=100)
    due_at: datetime | None = None
    suggested_for_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    priority_score: int | None = Field(default=None, ge=1, le=100)
    status: str | None = None
    due_at: datetime | None = None
    suggested_for_date: date | None = None


class TaskRead(BaseModel):
    id: int
    user_id: str
    brain_dump_id: str | None
    title: str
    description: str | None
    category: str
    priority_score: int
    status: str
    due_at: datetime | None
    suggested_for_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
