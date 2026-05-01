"""Nexa Next gateway runtime persistence — missions, tasks, artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NexaMission(Base):
    __tablename__ = "nexa_missions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class NexaMissionTask(Base):
    __tablename__ = "nexa_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_handle: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(512))
    task: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(32), default="queued")
    depends_on: Mapped[Any] = mapped_column(JSON, default=list)
    output_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)


class NexaArtifact(Base):
    __tablename__ = "nexa_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_handle: Mapped[str] = mapped_column(String(128))
    artifact_json: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
