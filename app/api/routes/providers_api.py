# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 2 Step 3 — provider CLI inventory API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_valid_web_user_id
from app.providers.intelligence_service import scan_providers_inventory
from app.providers.provider_registry import get_provider_spec
from app.providers.provider_sessions import probe_provider_session
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state

router = APIRouter(prefix="/providers", tags=["providers"])


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


__all__ = ["router"]
