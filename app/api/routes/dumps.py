from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.schemas.dump import BrainDumpCreate, BrainDumpRead
from app.services.dump_service import DumpService

router = APIRouter(prefix="/dumps", tags=["dumps"])
service = DumpService()


@router.post("", response_model=BrainDumpRead, status_code=status.HTTP_201_CREATED)
def create_dump(payload: BrainDumpCreate, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.create_dump(db, user_id, payload.text, payload.input_source)


@router.get("/{dump_id}", response_model=BrainDumpRead)
def get_dump(dump_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    row = service.get_dump(db, dump_id, user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brain dump not found")
    return row
