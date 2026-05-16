# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime plugin marketplace APIs (Phase 3 Step 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.plugins.plugin_installer import load_installed_manifest
from app.marketplace.runtime_marketplace import (
    get_marketplace_plugin,
    list_marketplace_plugins,
    marketplace_install,
    marketplace_summary,
    marketplace_uninstall,
    marketplace_upgrade,
)
from app.services.user_capabilities import (
    get_telegram_role_for_app_user,
    is_owner_role,
    is_privileged_owner_for_web_mutations,
)

router = APIRouter(prefix="/marketplace", tags=["plugin-marketplace"])


def _require_owner(db: Session, app_user_id: str) -> None:
    if not (
        is_owner_role(get_telegram_role_for_app_user(db, app_user_id))
        or is_privileged_owner_for_web_mutations(db, app_user_id)
    ):
        raise HTTPException(status_code=403, detail="Plugin install requires owner privileges.")


class MarketplacePluginBody(BaseModel):
    plugin_id: str = Field(..., min_length=1, max_length=128)
    version: str | None = Field(default=None, max_length=64)


@router.get("/plugins")
def list_plugins(_: str = Depends(get_valid_web_user_id)) -> dict:
    return {"plugins": list_marketplace_plugins(), "summary": marketplace_summary()}


@router.get("/plugins/{plugin_id}")
def show_plugin(plugin_id: str, _: str = Depends(get_valid_web_user_id)) -> dict:
    row = get_marketplace_plugin(plugin_id)
    if not row:
        raise HTTPException(status_code=404, detail="Unknown plugin")
    installed = load_installed_manifest(plugin_id)
    return {"plugin": row, "installed_manifest": installed}


@router.post("/install")
def install_route(
    body: MarketplacePluginBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    _require_owner(db, app_user_id)
    try:
        return marketplace_install(body.plugin_id.strip(), version=body.version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/uninstall")
def uninstall_route(
    body: MarketplacePluginBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    _require_owner(db, app_user_id)
    try:
        return marketplace_uninstall(body.plugin_id.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upgrade")
def upgrade_route(
    body: MarketplacePluginBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    _require_owner(db, app_user_id)
    try:
        return marketplace_upgrade(body.plugin_id.strip(), version=body.version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
