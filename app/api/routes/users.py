from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.db import get_db
from app.services.user_service import UserService
from app.services.channel_gateway.telegram_adapter import get_telegram_adapter

router = APIRouter(prefix="/users", tags=["users"])
user_service = UserService()

class AutoInitPayload(BaseModel):
    chat_id: str
    username: Optional[str] = None

@router.post("/auto-init")
async def auto_init_user(payload: AutoInitPayload, db: Session = Depends(get_db)):
    """API endpoint for auto-initialization from Web UI or other clients."""
    try:
        tg_user_id = int(payload.chat_id)
    except ValueError:
        tg_user_id = 0

    adapter = get_telegram_adapter()
    app_user_id = adapter._telegram.link_user(
        db,
        telegram_user_id=tg_user_id,
        chat_id=payload.chat_id,
        username=payload.username
    )
    user = user_service.get_or_create(db, app_user_id)
    return {"initialized": True, "user_id": user.id}
