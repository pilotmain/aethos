"""Scheduled autonomous missions (Phase 22)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NexaSchedulerJob(Base):
    __tablename__ = "nexa_scheduler_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str] = mapped_column(String(512), default="")
    mission_text: Mapped[str] = mapped_column(Text(), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="interval")  # interval | cron
    interval_seconds: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
