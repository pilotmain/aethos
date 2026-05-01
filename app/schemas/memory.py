from pydantic import BaseModel, Field


class PreferencesRead(BaseModel):
    planning_style: str = "gentle"
    max_daily_tasks: int = 3
    typical_gym_days: list[str] = []


class PreferencesUpdate(BaseModel):
    planning_style: str | None = Field(default=None)
    max_daily_tasks: int | None = Field(default=None, ge=1, le=10)
    typical_gym_days: list[str] | None = None


class MemoryNoteRead(BaseModel):
    key: str
    category: str
    content: str
    summary: str
    source: str


class MemoryNoteUpdateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2000)
    category: str | None = Field(default=None, max_length=64)


class MemoryNoteDeleteRequest(BaseModel):
    key: str = Field(min_length=1, max_length=255)


class MemoryRememberRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="note", max_length=64)


class MemoryForgetRequest(BaseModel):
    query: str = Field(min_length=1, max_length=255)


class MemoryForgetResult(BaseModel):
    deleted_notes: int
    deleted_tasks: int
    cancelled_checkins: int
    query: str
    deleted_task_ids: list[int] = []
    cancelled_checkin_ids: list[int] = []
    deleted_task_titles: list[str] = []


class SoulUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)


class AgentMemoryState(BaseModel):
    preferences: PreferencesRead
    soul_markdown: str
    memory_markdown: str
    notes: list[MemoryNoteRead]
