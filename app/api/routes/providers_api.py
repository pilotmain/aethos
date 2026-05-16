# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 2 Step 3–4 — provider CLI inventory + autonomous operator actions API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_valid_web_user_id
from app.deploy_context.context_execution import (
    execute_vercel_logs,
    execute_vercel_redeploy,
    execute_vercel_restart,
    execute_vercel_status,
)
from app.deploy_context.context_resolution import build_deploy_context
from app.deploy_context.errors import OperatorDeployError
from app.providers.actions import vercel_actions
from app.providers.intelligence_service import scan_providers_inventory
from app.providers.provider_registry import get_provider_spec
from app.providers.provider_sessions import probe_provider_session
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderProjectActionBody(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=200)
    environment: str = Field(default="production", max_length=32)


def _require_vercel(provider_id: str) -> None:
    if (provider_id or "").strip().lower() != "vercel":
        raise HTTPException(
            status_code=400,
            detail={
                "error_class": "DeploymentContextError",
                "message": "Provider actions are implemented for Vercel first.",
                "suggestions": [],
                "details": {},
            },
        )


@router.get("/")
def list_providers(_: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    """Return persisted provider inventory from ``aethos.json`` (no subprocess)."""
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    return st.get("provider_inventory") or {"providers": {}, "last_scanned_at": None}


@router.post("/scan")
def scan_providers(_: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    """Run non-destructive CLI probes and persist inventory."""
    return scan_providers_inventory(persist=True)


@router.post("/{provider_id}/redeploy")
def provider_redeploy(
    provider_id: str,
    body: ProviderProjectActionBody,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_vercel(provider_id)
    try:
        return execute_vercel_redeploy(body.project_id, environment=body.environment)
    except OperatorDeployError as exc:
        raise HTTPException(status_code=400, detail=exc.to_payload()) from exc


@router.post("/{provider_id}/restart")
def provider_restart(
    provider_id: str,
    body: ProviderProjectActionBody,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_vercel(provider_id)
    try:
        return execute_vercel_restart(body.project_id, environment=body.environment)
    except OperatorDeployError as exc:
        raise HTTPException(status_code=400, detail=exc.to_payload()) from exc


@router.get("/{provider_id}/deployments")
def provider_list_deployments(
    provider_id: str,
    _: str = Depends(get_valid_web_user_id),
    project_id: str = Query(..., min_length=1, max_length=200),
    environment: str = Query(default="production", max_length=32),
) -> dict[str, Any]:
    _require_vercel(provider_id)
    try:
        ctx = build_deploy_context(project_id, provider="vercel", environment=environment)
    except OperatorDeployError as exc:
        raise HTTPException(status_code=400, detail=exc.to_payload()) from exc
    return vercel_actions.list_deployments(ctx, environment=environment)


@router.get("/{provider_id}/status")
def provider_deployment_status(
    provider_id: str,
    _: str = Depends(get_valid_web_user_id),
    project_id: str = Query(..., min_length=1, max_length=200),
    environment: str = Query(default="production", max_length=32),
) -> dict[str, Any]:
    _require_vercel(provider_id)
    try:
        return execute_vercel_status(project_id, environment=environment)
    except OperatorDeployError as exc:
        raise HTTPException(status_code=400, detail=exc.to_payload()) from exc


@router.get("/{provider_id}/logs")
def provider_logs(
    provider_id: str,
    _: str = Depends(get_valid_web_user_id),
    project_id: str = Query(..., min_length=1, max_length=200),
    environment: str = Query(default="production", max_length=32),
    limit: int = Query(default=80, ge=10, le=300),
) -> dict[str, Any]:
    _require_vercel(provider_id)
    try:
        return execute_vercel_logs(project_id, environment=environment, limit=limit)
    except OperatorDeployError as exc:
        raise HTTPException(status_code=400, detail=exc.to_payload()) from exc


@router.get("/{provider_id}/projects")
def list_provider_projects(provider_id: str, _: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    if pid != "vercel":
        return {"provider": pid, "projects": [], "note": "project listing implemented for vercel first"}
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    inv = (st.get("provider_inventory") or {}).get("providers") or {}
    row = inv.get("vercel")
    if isinstance(row, dict) and isinstance(row.get("projects"), list):
        return {"provider": "vercel", "projects": row.get("projects") or []}
    from app.core.config import get_settings

    s = get_settings()
    timeout = float(getattr(s, "aethos_provider_cli_timeout_sec", 20) or 20)
    fresh = probe_provider_session("vercel", timeout_sec=timeout)
    return {"provider": "vercel", "projects": fresh.get("projects") or [], "live": True}


@router.get("/{provider_id}")
def show_provider(provider_id: str, _: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    if (provider_id or "").strip().lower() == "scan":
        raise HTTPException(status_code=404, detail="Not found")
    if not get_provider_spec(provider_id):
        raise HTTPException(status_code=404, detail="Unknown provider")
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    inv = (st.get("provider_inventory") or {}).get("providers") or {}
    row = inv.get((provider_id or "").strip().lower())
    if isinstance(row, dict):
        return row
    from app.core.config import get_settings

    s = get_settings()
    timeout = float(getattr(s, "aethos_provider_cli_timeout_sec", 20) or 20)
    return probe_provider_session(provider_id, timeout_sec=timeout)


__all__ = ["router"]
