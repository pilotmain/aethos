# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin marketplace foundation APIs (Phase 2 Step 9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_valid_web_user_id
from app.plugins.plugin_loader import load_all_plugins
from app.plugins.plugin_registry import get_plugin_manifest, list_plugin_manifests
from app.plugins.plugin_runtime import disable_plugin, load_plugin

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginLoadBody(BaseModel):
    plugin_id: str = Field(..., min_length=1, max_length=128)


@router.get("/")
def list_plugins(_: str = Depends(get_valid_web_user_id)) -> dict:
    return {"plugins": list_plugin_manifests()}


@router.get("/{plugin_id}")
def show_plugin(plugin_id: str, _: str = Depends(get_valid_web_user_id)) -> dict:
    row = get_plugin_manifest(plugin_id)
    if not row:
        raise HTTPException(status_code=404, detail="Unknown plugin")
    return row


@router.post("/load")
def load_plugin_route(body: PluginLoadBody, _: str = Depends(get_valid_web_user_id)) -> dict:
    return load_plugin(body.plugin_id.strip())


@router.post("/disable")
def disable_plugin_route(body: PluginLoadBody, _: str = Depends(get_valid_web_user_id)) -> dict:
    return disable_plugin(body.plugin_id.strip())


@router.post("/bootstrap")
def bootstrap_plugins(_: str = Depends(get_valid_web_user_id)) -> dict:
    return load_all_plugins()
