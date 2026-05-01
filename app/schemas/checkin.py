from datetime import datetime

from pydantic import BaseModel


class CheckInRead(BaseModel):
    id: int
    user_id: str
    task_id: int
    prompt_text: str
    scheduled_for: datetime
    sent_at: datetime | None
    response_text: str | None
    response_type: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckInRespondRequest(BaseModel):
    checkin_id: int
    response_text: str
