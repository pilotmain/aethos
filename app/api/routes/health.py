from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
def healthcheck() -> HealthRead:
    settings = get_settings()
    return HealthRead(status="ok", app=settings.app_name, env=settings.app_env)
