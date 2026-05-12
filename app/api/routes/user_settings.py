# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""User settings API (Phase 20) — persisted preferences + identity headers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.user_settings.service import get_settings_document, upsert_settings

router = APIRouter(prefix="/user", tags=["user"])


class UserSettingsUpdate(BaseModel):
    privacy_mode: str | None = None
    ui_preferences: dict[str, Any] | None = Field(default=None, description="Partial merge into stored UI preferences")
    # Phase 38 — also accepted at root for convenience; merged into ui_preferences
    token_budget_per_request: int | None = None
    daily_cost_budget_usd: float | None = None
    show_payload_summary: bool | None = None
    allow_large_context: bool | None = None


@router.get("/settings")
def get_user_settings(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict[str, Any]:
    doc = get_settings_document(db, app_user_id, session_id=x_session_id, device_id=x_device_id)
    ui = doc.get("ui_preferences") or {}
    return {
        "privacy_mode": doc["privacy_mode"],
        "ui_preferences": doc["ui_preferences"],
        "identity": doc["identity"],
        "token_budget_per_request": ui.get("token_budget_per_request"),
        "daily_cost_budget_usd": ui.get("daily_cost_budget_usd"),
        "show_payload_summary": ui.get("show_payload_summary"),
        "allow_large_context": ui.get("allow_large_context"),
    }


@router.post("/settings")
def post_user_settings(
    body: UserSettingsUpdate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    merged_ui = dict(body.ui_preferences or {})
    if body.token_budget_per_request is not None:
        merged_ui["token_budget_per_request"] = body.token_budget_per_request
    if body.daily_cost_budget_usd is not None:
        merged_ui["daily_cost_budget_usd"] = body.daily_cost_budget_usd
    if body.show_payload_summary is not None:
        merged_ui["show_payload_summary"] = body.show_payload_summary
    if body.allow_large_context is not None:
        merged_ui["allow_large_context"] = body.allow_large_context
    prefs_in = merged_ui if merged_ui else body.ui_preferences
    out = upsert_settings(
        db,
        app_user_id,
        privacy_mode=body.privacy_mode,
        ui_preferences=prefs_in,
    )
    return {
        "privacy_mode": out["privacy_mode"],
        "ui_preferences": out["ui_preferences"],
        "identity": {"session_id": None, "device_id": None},
    }
