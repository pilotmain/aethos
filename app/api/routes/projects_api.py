# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 2 Step 3–4 — local project registry + deploy confidence API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_valid_web_user_id
from app.deploy_context.context_validation import workspace_confidence
from app.deploy_context.context_resolution import build_deploy_context
from app.deploy_context.errors import OperatorDeployError
from app.projects.project_registry_service import link_project_repo, scan_projects_registry
from app.runtime.runtime_state import (
    ensure_operator_context_schema,
    load_runtime_state,
    save_runtime_state,
    utc_now_iso,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class LinkBody(BaseModel):
    repo_path: str = Field(..., min_length=1, max_length=4096)


class ResolveBody(BaseModel):
    provider: str = Field(default="vercel", max_length=32)
    environment: str = Field(default="production", max_length=32)


@router.get("/")
def list_projects(_: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    return st.get("project_registry") or {"projects": {}, "last_scanned_at": None}


@router.post("/scan")
def scan_projects(_: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    return scan_projects_registry(persist=True)


@router.post("/{project_id}/resolve")
def resolve_project_deploy_context(
    project_id: str,
    body: ResolveBody,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    try:
        ctx = build_deploy_context(
            project_id,
            provider=body.provider,
            environment=body.environment,
        )
    except OperatorDeployError as exc:
        raise HTTPException(status_code=400, detail=exc.to_payload()) from exc
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    hist = st.setdefault("project_resolution_history", [])
    if isinstance(hist, list):
        hist.append(
            {
                "ts": utc_now_iso(),
                "action": "resolve",
                "project_id": ctx.get("project_id"),
                "provider": ctx.get("provider"),
                "repo_path": ctx.get("repo_path"),
            }
        )
        st["project_resolution_history"] = hist[-200:]
        save_runtime_state(st)
    return {"ok": True, "context": ctx}


@router.get("/{project_id}/confidence")
def project_confidence(project_id: str, _: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    pid = (project_id or "").strip().lower()
    if pid in ("resolve", "confidence", "scan", "link"):
        raise HTTPException(status_code=404, detail="Not found")
    projects = ((st.get("project_registry") or {}).get("projects") or {})
    row = projects.get(pid)
    if not isinstance(row, dict):
        raise HTTPException(status_code=404, detail="Unknown project")
    rp = row.get("repo_path")
    cache = (st.get("provider_resolution_cache") or {}).get(pid) if isinstance(st.get("provider_resolution_cache"), dict) else None
    if not rp:
        return {
            "project_id": pid,
            "workspace_confidence": "low",
            "signals": [],
            "provider_resolution_cache": cache,
            "note": "No repo_path linked for this project.",
        }
    try:
        p = Path(str(rp)).expanduser().resolve()
        if not p.is_dir():
            raise OSError
        conf = workspace_confidence(p)
    except OSError:
        return {
            "project_id": pid,
            "workspace_confidence": "low",
            "signals": [],
            "provider_resolution_cache": cache,
            "note": "Linked repo_path is not reachable.",
        }
    return {"project_id": pid, **conf, "provider_resolution_cache": cache}


@router.post("/{project_id}/link")
def link_project(
    project_id: str,
    body: LinkBody,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    out = link_project_repo(project_id, body.repo_path, persist=True)
    if not out:
        raise HTTPException(status_code=400, detail="Invalid project id")
    return {"ok": True, "project": out}


@router.get("/{project_id}")
def show_project(project_id: str, _: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    projects = ((st.get("project_registry") or {}).get("projects") or {})
    row = projects.get((project_id or "").strip().lower())
    if not isinstance(row, dict):
        raise HTTPException(status_code=404, detail="Unknown project")
    return row


__all__ = ["router"]
