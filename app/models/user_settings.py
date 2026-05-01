"""Per-user Nexa preferences (Phase 20) — privacy mode + UI prefs persisted in DB."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NexaUserSettings(Base):
    """One row per authenticated web user (``user_id`` matches Mission Control / gateway)."""

    __tablename__ = "nexa_user_settings"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    privacy_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ui_preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
