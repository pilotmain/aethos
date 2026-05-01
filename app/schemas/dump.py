from datetime import datetime

from pydantic import BaseModel, Field


class BrainDumpCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    input_source: str = "text"


class BrainDumpRead(BaseModel):
    id: str
    user_id: str
    input_text: str
    input_source: str
    emotional_state: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
