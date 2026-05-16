# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 2 Step 3 — local project registry API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_valid_web_user_id
from app.projects.project_registry_service import link_project_repo, scan_projects_registry
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state


router = APIRouter(prefix="/projects", tags=["projects"])


class LinkBody(BaseModel):
    repo_path: str = Field(..., min_length=1, max_length=4096)


@router.get("/")
def list_projects(_: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    return st.get("project_registry") or {"projects": {}, "last_scanned_at": None}


@router.post("/scan")
def scan_projects(_: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    return scan_projects_registry(persist=True)


@router.get("/{project_id}")
def show_project(project_id: str, _: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    projects = ((st.get("project_registry") or {}).get("projects") or {})
    row = projects.get((project_id or "").strip().lower())
    if not isinstance(row, dict):
        raise HTTPException(status_code=404, detail="Unknown project")
    return row


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


__all__ = ["router"]
