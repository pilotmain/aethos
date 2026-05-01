from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.schemas.checkin import CheckInRead, CheckInRespondRequest
from app.services.checkin_service import CheckInService

router = APIRouter(prefix="/checkins", tags=["checkins"])
service = CheckInService()


@router.get("/pending", response_model=list[CheckInRead])
def list_pending(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.list_pending(db, user_id)


@router.post("/respond")
def respond(payload: CheckInRespondRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.respond(db, user_id, payload.checkin_id, payload.response_text)


@router.post("/{checkin_id}/cancel")
def cancel_checkin(checkin_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.cancel(db, user_id, checkin_id)
