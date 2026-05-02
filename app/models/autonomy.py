"""Phase 44 — persistent autonomous tasks, feedback, and decision logs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NexaAutonomousTask(Base):
    """User-visible autonomous work queue (interruptible)."""

    __tablename__ = "nexa_autonomous_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    auto_generated: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    origin: Mapped[str] = mapped_column(String(64), default="autonomy", nullable=False)
    context_json: Mapped[str] = mapped_column(Text(), default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)


class NexaTaskFeedback(Base):
    """Outcome log for learning loops (Phase 44F)."""

    __tablename__ = "nexa_task_feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    task_id: Mapped[str] = mapped_column(String(128), index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), default="", nullable=False)
    meta_json: Mapped[str] = mapped_column(Text(), default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class NexaAutonomyDecisionLog(Base):
    """Summaries of autonomous decision cycles for Mission Control."""

    __tablename__ = "nexa_autonomy_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    summary: Mapped[str] = mapped_column(Text(), nullable=False)
    detail_json: Mapped[str] = mapped_column(Text(), default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


__all__ = ["NexaAutonomousTask", "NexaAutonomyDecisionLog", "NexaTaskFeedback"]
