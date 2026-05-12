# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Cron automation API — Phase 13 (Bearer ``NEXA_CRON_API_TOKEN``)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import verify_cron_token
from app.services.cron.models import JobActionType
from app.services.cron.scheduler import get_nexa_cron_scheduler

router = APIRouter(prefix="/cron", tags=["cron"])


class CronJobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    cron_expression: str = Field(..., min_length=9, max_length=128)
    action_type: Literal["skill", "host_action", "channel_message", "chain", "webhook"] = "channel_message"
    action_payload: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = Field(default=None, max_length=128)
    created_by_channel: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)


@router.post("/jobs")
def cron_create_job(
    body: CronJobCreate,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    sched = get_nexa_cron_scheduler()
    try:
        job = sched.add_job(
            name=body.name,
            cron_expression=body.cron_expression.strip(),
            action_type=JobActionType(body.action_type),
            action_payload=body.action_payload,
            created_by=body.created_by,
            created_by_channel=body.created_by_channel,
            timezone=body.timezone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"ok": True, "job": job.to_dict()}


@router.get("/jobs")
def cron_list_jobs(_: None = Depends(verify_cron_token)) -> dict[str, Any]:
    jobs = get_nexa_cron_scheduler().list_jobs()
    return {"ok": True, "jobs": [j.to_dict() for j in jobs]}


@router.delete("/jobs/{job_id}")
def cron_delete_job(job_id: str, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    ok = get_nexa_cron_scheduler().remove_job(job_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return {"ok": True}


@router.post("/jobs/{job_id}/pause")
def cron_pause_job(job_id: str, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    ok = get_nexa_cron_scheduler().pause_job(job_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return {"ok": True}


@router.post("/jobs/{job_id}/resume")
def cron_resume_job(job_id: str, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    ok = get_nexa_cron_scheduler().resume_job(job_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return {"ok": True}


__all__ = ["router"]
