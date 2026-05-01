from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.services.user_service import UserService

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
