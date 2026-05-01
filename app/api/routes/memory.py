from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.schemas.memory import (
    AgentMemoryState,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryNoteDeleteRequest,
    MemoryNoteRead,
    MemoryNoteUpdateRequest,
    MemoryRememberRequest,
    PreferencesRead,
    PreferencesUpdate,
    SoulUpdateRequest,
)
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])
service = MemoryService()


@router.get("", response_model=PreferencesRead)
def get_memory(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.get_preferences(db, user_id)


@router.put("/preferences", response_model=PreferencesRead)
def update_preferences(payload: PreferencesUpdate, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.update_preferences(db, user_id, payload)


@router.get("/state", response_model=AgentMemoryState)
def get_memory_state(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.get_state(db, user_id)


@router.post("/remember", response_model=MemoryNoteRead)
def remember(payload: MemoryRememberRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.remember_note(db, user_id, payload.content, category=payload.category, source="api")


@router.patch("/notes", response_model=MemoryNoteRead)
def update_note(payload: MemoryNoteUpdateRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.update_note(db, user_id, payload.key, payload.content, category=payload.category, source="api")


@router.post("/notes/delete")
def delete_note(payload: MemoryNoteDeleteRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return {"deleted": service.delete_note(db, user_id, payload.key)}


@router.post("/forget", response_model=MemoryForgetResult)
def forget(payload: MemoryForgetRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.forget(db, user_id, payload.query)


@router.put("/soul", response_model=str)
def update_soul(payload: SoulUpdateRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.update_soul_markdown(db, user_id, payload.content, source="api")
