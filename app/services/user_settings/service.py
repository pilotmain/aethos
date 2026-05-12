# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Load and persist per-user Nexa settings (privacy mode + UI preferences)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user_settings import NexaUserSettings
from app.services.privacy_firewall.user_privacy import UserPrivacyMode, normalize_user_privacy_mode


def effective_privacy_mode(db: Session | None, user_id: str | None) -> UserPrivacyMode:
    """DB preference when set; otherwise env ``NEXA_USER_PRIVACY_MODE``."""
    if db is not None and user_id:
        row = db.get(NexaUserSettings, user_id)
        if row is not None and (row.privacy_mode or "").strip():
            return normalize_user_privacy_mode(row.privacy_mode)
    s = get_settings()
    return normalize_user_privacy_mode(getattr(s, "nexa_user_privacy_mode", None))


def _default_ui_preferences() -> dict[str, Any]:
    return {
        "theme": "dark",
        "auto_refresh": True,
        # Phase 38 — token economy (None = use server env defaults)
        "token_budget_per_request": None,
        "daily_cost_budget_usd": None,
        "show_payload_summary": True,
        "allow_large_context": False,
    }


def get_settings_document(
    db: Session,
    user_id: str,
    *,
    session_id: str | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    row = db.get(NexaUserSettings, user_id)
    ui = dict(_default_ui_preferences())
    stored_privacy: str | None = None
    if row is not None:
        if isinstance(row.ui_preferences, dict):
            ui.update(row.ui_preferences)
        if (row.privacy_mode or "").strip():
            stored_privacy = normalize_user_privacy_mode(row.privacy_mode)

    effective = stored_privacy if stored_privacy else normalize_user_privacy_mode(get_settings().nexa_user_privacy_mode)
    return {
        "privacy_mode": effective,
        "privacy_source": "database" if stored_privacy else "environment_default",
        "ui_preferences": ui,
        "identity": {
            "session_id": session_id,
            "device_id": device_id,
        },
    }


def upsert_settings(
    db: Session,
    user_id: str,
    *,
    privacy_mode: str | None = None,
    ui_preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = db.get(NexaUserSettings, user_id)
    if row is None:
        row = NexaUserSettings(user_id=user_id, privacy_mode=None, ui_preferences={})
        db.add(row)

    if privacy_mode is not None:
        row.privacy_mode = normalize_user_privacy_mode(privacy_mode)

    if ui_preferences is not None:
        merged = dict(_default_ui_preferences())
        if isinstance(row.ui_preferences, dict):
            merged.update(row.ui_preferences)
        merged.update(ui_preferences)
        row.ui_preferences = merged

    db.commit()
    db.refresh(row)
    return get_settings_document(db, user_id)
