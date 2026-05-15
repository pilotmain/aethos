# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deployment + environment + operational workflow APIs (OpenClaw infra parity)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.paths import get_aethos_home_dir
from app.core.security import get_valid_web_user_id
from app.deployments import deployment_rollback
from app.deployments.deployment_registry import get_deployment, list_deployments_for_user
from app.environments import environment_registry
from app.operations import operations_runtime
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

router = APIRouter(prefix="", tags=["deployments-environments"])


def _belongs(row: dict[str, Any], app_user_id: str) -> bool:
    return str(row.get("user_id") or "") == str(app_user_id)


@router.get("/deployments")
def list_deployments(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    rows = list_deployments_for_user(st, app_user_id)
    return {"deployments": rows, "count": len(rows)}


@router.get("/deployments/{deployment_id}")
def get_deployment_detail(deployment_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_deployment(st, deployment_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return {"deployment": row}


@router.get("/deployments/{deployment_id}/artifacts")
def get_deployment_artifacts(deployment_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_deployment(st, deployment_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    arts = row.get("artifacts")
    return {"deployment_id": deployment_id, "artifacts": arts if isinstance(arts, list) else []}


@router.get("/deployments/{deployment_id}/logs")
def get_deployment_logs(
    deployment_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
    lines: int = 120,
) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_deployment(st, deployment_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    mem = row.get("logs")
    mem_lines: list[str] = []
    if isinstance(mem, list):
        for item in mem[-lines:]:
            if isinstance(item, dict):
                mem_lines.append(json.dumps(item, ensure_ascii=False))
            else:
                mem_lines.append(str(item))
    file_hits: list[str] = []
    p = get_aethos_home_dir() / "logs" / "deployments.log"
    if p.is_file():
        try:
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if deployment_id in ln:
                    file_hits.append(ln)
        except OSError:
            pass
    return {"deployment_id": deployment_id, "memory": mem_lines[-lines:], "file_tail": file_hits[-lines:]}


@router.post("/deployments/{deployment_id}/rollback")
def post_deployment_rollback(
    deployment_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_deployment(st, deployment_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    reason = ""
    if isinstance(body, dict):
        reason = str(body.get("reason") or "")
    out = deployment_rollback.start_rollback(st, deployment_id, reason=reason)
    if not out:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Rollback not available")
    save_runtime_state(st)
    return {"deployment": out}


@router.get("/environments")
def list_environments(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    rows = environment_registry.list_environments_for_user(st, app_user_id)
    return {"environments": rows, "count": len(rows)}


@router.get("/environments/{environment_id}")
def get_environment_detail(environment_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    row = environment_registry.get_environment(st, environment_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return {"environment": row}


class OperationRunBody(BaseModel):
    op_type: str = Field(..., description="deploy | rollback | restart | repair | cleanup | backup | restore | health_check")
    environment_id: str | None = None
    payload: dict[str, Any] | None = None


@router.get("/operations")
def list_ops(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    rows = operations_runtime.list_operations(st, user_id=app_user_id)
    return {"operations": rows, "count": len(rows)}


@router.post("/operations/run")
def post_operation_run(body: OperationRunBody, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    try:
        rec = operations_runtime.enqueue_operation(
            st,
            body.op_type,
            user_id=app_user_id,
            environment_id=body.environment_id,
            payload=body.payload,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    save_runtime_state(st)
    return {"operation": rec}
