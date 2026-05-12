# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 23–24 — dev workspaces + runs API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.dev_runtime import NexaDevRun, NexaDevStep
from app.services.dev_runtime.service import run_dev_mission
from app.services.dev_runtime.workspace import list_workspaces, register_workspace
from app.services.scheduler.service import NexaSchedulerService

router = APIRouter(prefix="/dev", tags=["dev-runtime"])
_scheduler = NexaSchedulerService()


class WorkspaceCreate(BaseModel):
    name: str = Field("", max_length=512)
    repo_path: str = Field(..., min_length=1, max_length=4000)
    repo_url: str | None = Field(default=None, max_length=2000)
    branch: str | None = Field(default=None, max_length=512)


class DevRunCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=64)
    goal: str = Field(..., min_length=1, max_length=50_000)
    auto_pr: bool = False
    preferred_agent: str | None = Field(default=None, max_length=64)
    allow_write: bool = False
    allow_commit: bool = False
    allow_push: bool = False
    cost_budget_usd: float = Field(default=0, ge=0, le=1_000_000)
    max_iterations: int | None = Field(default=None)
    schedule: dict[str, Any] | None = None


def _workspace_row(w: Any) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.name,
        "repo_path": w.repo_path,
        "repo_url": w.repo_url,
        "branch": w.branch,
        "status": w.status,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


def _run_row(r: NexaDevRun, *, steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": r.id,
        "workspace_id": r.workspace_id,
        "mission_id": r.mission_id,
        "goal": r.goal,
        "status": r.status,
        "plan_json": r.plan_json,
        "result_json": r.result_json,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "error": r.error,
    }
    if steps is not None:
        out["steps"] = steps
    return out


def _schedule_dev_mission(db: Session, app_user_id: str, body: DevRunCreate) -> dict[str, Any]:
    sched = body.schedule or {}
    cron = str(sched.get("cron") or "").strip()
    interval = sched.get("interval_seconds")
    payload = {
        "type": "dev_mission",
        "workspace_id": body.workspace_id,
        "goal": body.goal,
        "preferred_agent": body.preferred_agent or "local_stub",
        "allow_write": bool(body.allow_write),
        "max_iterations": body.max_iterations if body.max_iterations is not None else 3,
    }
    mission_text = json.dumps(payload)
    label = f"dev:{body.workspace_id[:24]}"
    if cron:
        row = _scheduler.create_job(
            db,
            user_id=app_user_id,
            mission_text=mission_text,
            kind="cron",
            cron_expression=cron,
            interval_seconds=None,
            label=label,
        )
    elif interval is not None:
        row = _scheduler.create_job(
            db,
            user_id=app_user_id,
            mission_text=mission_text,
            kind="interval",
            interval_seconds=int(interval),
            cron_expression=None,
            label=label,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="schedule requires cron or interval_seconds",
        )
    return {
        "ok": True,
        "scheduler_job_id": row.id,
        "dev_mission_payload": payload,
    }


@router.post("/workspaces")
def post_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    try:
        row = register_workspace(
            db,
            app_user_id,
            body.name,
            body.repo_path,
            repo_url=body.repo_url,
            branch=body.branch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"ok": True, "workspace": _workspace_row(row)}


@router.get("/workspaces")
def get_workspaces(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    rows = list_workspaces(db, app_user_id)
    return {"ok": True, "workspaces": [_workspace_row(w) for w in rows]}


@router.get("/workspaces/{workspace_id}")
def get_workspace_route(
    workspace_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    from app.services.dev_runtime.workspace import get_workspace

    w = get_workspace(db, app_user_id, workspace_id)
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace_not_found")
    return {"ok": True, "workspace": _workspace_row(w)}


@router.post("/runs")
def post_run(
    body: DevRunCreate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    if body.schedule:
        try:
            return _schedule_dev_mission(db, app_user_id, body)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        return run_dev_mission(
            db,
            app_user_id,
            body.workspace_id,
            body.goal,
            auto_pr=body.auto_pr,
            preferred_agent=body.preferred_agent,
            allow_write=body.allow_write,
            allow_commit=body.allow_commit,
            allow_push=body.allow_push,
            cost_budget_usd=float(body.cost_budget_usd or 0),
            max_iterations=body.max_iterations,
            schedule=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/runs/{run_id}/retry")
def post_retry_run(
    run_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    r = db.get(NexaDevRun, run_id)
    if r is None or r.user_id != app_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found")
    rj = r.result_json if isinstance(r.result_json, dict) else {}
    try:
        mi = rj.get("max_iterations")
        return run_dev_mission(
            db,
            app_user_id,
            r.workspace_id,
            r.goal,
            auto_pr=bool(rj.get("auto_pr", False)),
            preferred_agent=rj.get("preferred_agent"),
            allow_write=bool(rj.get("allow_write", False)),
            allow_commit=bool(rj.get("allow_commit", False)),
            allow_push=bool(rj.get("allow_push", False)),
            cost_budget_usd=float(rj.get("cost_budget_usd") or 0),
            max_iterations=int(mi) if mi is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/runs")
def list_runs(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(NexaDevRun)
            .where(NexaDevRun.user_id == app_user_id)
            .order_by(NexaDevRun.created_at.desc())
            .limit(60)
        ).all()
    )
    return {"ok": True, "runs": [_run_row(r) for r in rows]}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    r = db.get(NexaDevRun, run_id)
    if r is None or r.user_id != app_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found")
    step_rows = list(
        db.scalars(
            select(NexaDevStep).where(NexaDevStep.run_id == run_id).order_by(NexaDevStep.id.asc())
        ).all()
    )
    steps = [
        {
            "id": s.id,
            "step_type": s.step_type,
            "status": s.status,
            "command": s.command,
            "output": (s.output or "")[:120_000],
            "artifact_json": s.artifact_json,
            "iteration": getattr(s, "iteration", None),
            "adapter": getattr(s, "adapter", None),
            "input_json": getattr(s, "input_json", None),
            "output_json": getattr(s, "output_json", None),
            "test_result": getattr(s, "test_result", None),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in step_rows
    ]
    return {"ok": True, "run": _run_row(r, steps=steps)}


__all__ = ["router"]
