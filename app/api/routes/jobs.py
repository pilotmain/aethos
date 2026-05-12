# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.schemas.agent_job import AgentJobApprovalRequest, AgentJobCreate, AgentJobRead
from app.services.agent_job_service import AgentJobService

router = APIRouter(prefix="/jobs", tags=["jobs"])
service = AgentJobService()


@router.get("", response_model=list[AgentJobRead])
def list_jobs(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.list_jobs(db, user_id)


@router.post("", response_model=AgentJobRead)
def create_job(payload: AgentJobCreate, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.create_job(db, user_id, payload)


@router.get("/{job_id}", response_model=AgentJobRead)
def get_job(job_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.get_job(db, user_id, job_id)


@router.post("/{job_id}/decision", response_model=AgentJobRead)
def decide_job(
    job_id: int,
    payload: AgentJobApprovalRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return service.decide(db, user_id, job_id, payload.decision)


@router.post("/{job_id}/cancel", response_model=AgentJobRead)
def cancel_job(job_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.cancel(db, user_id, job_id)


@router.post("/{job_id}/review-approve", response_model=AgentJobRead)
def approve_review(job_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.approve_review(db, user_id, job_id)


@router.post("/{job_id}/commit-approve", response_model=AgentJobRead)
def approve_commit(job_id: int, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return service.approve_commit(db, user_id, job_id)
