from datetime import datetime

from pydantic import BaseModel, Field


class DevTaskCreate(BaseModel):
    title: str
    description: str


class DevTaskRead(BaseModel):
    id: int
    user_id: str
    source: str = "telegram"
    title: str
    description: str
    status: str
    branch_name: str | None = None
    commit_sha: str | None = None
    pr_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime = Field(description="last update time")

    model_config = {"from_attributes": True}
