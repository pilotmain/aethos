from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    app: str
    env: str
