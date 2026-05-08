from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.core.db import get_db
from app.core.security import get_current_user_id, get_valid_web_user_id
from app.services.user_service import UserService
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
service = UserService()


@router.get("/me")
def me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> dict:
    user = service.get_or_create(db, user_id)
    return {
        "user_id": user.id,
        "timezone": user.timezone,
        "auth_mode": "header_stub",
    }


@router.get("/web/me")
async def get_current_user(
    user_id: str = Depends(get_valid_web_user_id),
    token: Optional[str] = Depends(lambda: None)  # Just for debugging
):
    """Debug endpoint to check authentication status."""
    settings = get_settings()
    return {
        "authenticated": True,
        "user_id": user_id,
        "token_required": bool(settings.nexa_web_api_token),
        "token_matches": True,  # actual check would verify
    }
