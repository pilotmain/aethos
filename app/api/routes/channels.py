# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Channel gateway admin: configuration visibility (read-only, no secrets)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.user import User
from app.services.channel_gateway.governance import merge_channel_status_governance
from app.services.channel_gateway.status import build_channel_status_list

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelStatusOut(BaseModel):
    channel: str
    label: str
    available: bool
    configured: bool
    enabled: bool
    health: Literal["ok", "missing_config", "disabled", "unknown"]
    webhook_url: str | None = None
    webhook_urls: dict[str, str | None] | None = None
    missing: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    health_details: dict[str, str] | None = None
    # Phase 13 — present when ``NEXA_GOVERNANCE_ENABLED`` and an org context is resolved.
    governance_enabled: bool | None = None
    allowed_roles: list[str] | None = None
    approval_required: bool | None = None


class ChannelsStatusResponse(BaseModel):
    channels: list[ChannelStatusOut]


@router.get("/status", response_model=ChannelsStatusResponse)
def get_channels_status(
    db: Session = Depends(get_db),
    organization_id: str | None = Query(None, description="Optional org id; defaults to the caller's org or NEXA_DEFAULT_ORGANIZATION_ID."),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> ChannelsStatusResponse:
    """Which channels are configured (env presence only — no secret values)."""
    rows = build_channel_status_list()
    u = db.get(User, app_user_id)
    oid = (organization_id or "").strip() or None
    if not oid and u:
        oid = (u.organization_id or "").strip() or None
    if not oid:
        oid = (get_settings().nexa_default_organization_id or "").strip() or None
    rows = merge_channel_status_governance(db, rows, organization_id=oid)
    return ChannelsStatusResponse(channels=[ChannelStatusOut.model_validate(r) for r in rows])
