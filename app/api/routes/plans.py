# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.schemas.plan import GeneratePlanRequest, GeneratePlanResponse, PlanRead, PlanTaskReason
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/plans", tags=["plans"])
service = OrchestratorService()


def _to_plan_read(data: dict) -> PlanRead:
    return PlanRead(
        id=data["plan"].id,
        user_id=data["plan"].user_id,
        plan_date=data["plan"].plan_date,
        summary=data["plan"].summary,
        mode=data["plan"].mode,
        tasks=data["tasks"],
        reasons=[PlanTaskReason(**row) for row in data["reasons"]],
        created_at=data["plan"].created_at,
    )


@router.post("/generate", response_model=GeneratePlanResponse)
def generate_plan(payload: GeneratePlanRequest, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    result = service.generate_plan_from_text(
        db,
        user_id,
        payload.text,
        payload.input_source,
        intent="brain_dump",
    )
    if result.get("needs_more_context"):
        return GeneratePlanResponse(
            plan=None,
            needs_more_context=True,
            detected_state=result["detected_state"],
            extracted_tasks_count=result["extracted_tasks_count"],
        )
    return GeneratePlanResponse(
        plan=_to_plan_read(result["plan"]),
        needs_more_context=False,
        detected_state=result["detected_state"],
        extracted_tasks_count=result["extracted_tasks_count"],
    )


@router.get("/today", response_model=PlanRead)
def get_today_plan(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    result = service.get_today_plan(db, user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No plan for today")
    return _to_plan_read(result)


@router.post("/morning-refresh", response_model=PlanRead)
def morning_refresh(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    result = service.refresh_morning_plan(db, user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tasks available to build a plan")
    return _to_plan_read(result)
