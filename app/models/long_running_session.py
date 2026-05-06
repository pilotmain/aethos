"""Persistent long-running agent sessions (Phase 42)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NexaLongRunningSession(Base):
    __tablename__ = "aethos_long_running_sessions"
    __table_args__ = (UniqueConstraint("user_id", "session_key", name="uq_lr_user_session"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    session_key: Mapped[str] = mapped_column(String(128))
    goal: Mapped[str] = mapped_column(Text(), default="")
    state_json: Mapped[str] = mapped_column(Text(), default="{}")
    interval_seconds: Mapped[int] = mapped_column(Integer(), default=300)
    iteration: Mapped[int] = mapped_column(Integer(), default=0)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    # Phase 44 — align with unified task metadata (defaults preserve existing rows).
    auto_generated: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    origin: Mapped[str] = mapped_column(String(64), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
