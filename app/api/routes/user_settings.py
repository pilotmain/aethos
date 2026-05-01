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


@router.get("/settings")
def get_user_settings(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict[str, Any]:
    doc = get_settings_document(db, app_user_id, session_id=x_session_id, device_id=x_device_id)
    return {
        "privacy_mode": doc["privacy_mode"],
        "ui_preferences": doc["ui_preferences"],
        "identity": doc["identity"],
    }


@router.post("/settings")
def post_user_settings(
    body: UserSettingsUpdate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    out = upsert_settings(
        db,
        app_user_id,
        privacy_mode=body.privacy_mode,
        ui_preferences=body.ui_preferences,
    )
    return {
        "privacy_mode": out["privacy_mode"],
        "ui_preferences": out["ui_preferences"],
        "identity": {"session_id": None, "device_id": None},
    }
