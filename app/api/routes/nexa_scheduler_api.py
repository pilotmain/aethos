# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Scheduler API — `/api/v1/scheduler/*` (Phase 22)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.scheduler.service import NexaSchedulerService

router = APIRouter(prefix="/scheduler", tags=["scheduler"])
_svc = NexaSchedulerService()


class SchedulerCreate(BaseModel):
    mission_text: str = Field(..., min_length=1, max_length=50000)
    kind: Literal["interval", "cron"] = "interval"
    interval_seconds: int | None = Field(default=None, ge=60, le=86400 * 365)
    cron_expression: str | None = Field(default=None, max_length=128)
    label: str = Field(default="", max_length=512)


@router.post("/create")
def scheduler_create(
    body: SchedulerCreate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    if body.kind == "interval":
        if not body.interval_seconds:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="interval_seconds required for interval jobs",
            )
    elif body.kind == "cron":
        if not (body.cron_expression or "").strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="cron_expression required for cron jobs",
            )
    row = _svc.create_job(
        db,
        user_id=app_user_id,
        mission_text=body.mission_text,
        kind=body.kind,
        interval_seconds=body.interval_seconds,
        cron_expression=body.cron_expression,
        label=body.label,
    )
    return {"ok": True, "id": row.id}


@router.get("/list")
def scheduler_list(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    return {"ok": True, "jobs": _svc.list_jobs(db, app_user_id)}


@router.delete("/{job_id}")
def scheduler_delete(
    job_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    if not _svc.delete_job(db, user_id=app_user_id, job_id=job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {"ok": True}


__all__ = ["router"]
