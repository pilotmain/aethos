"""Registered projects for multi-cloud / multi-repo Nexa Ops and Dev agents."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    idea_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    repo_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    provider_key: Mapped[str] = mapped_column(String(100), nullable=False, default="local")
    default_environment: Mapped[str] = mapped_column(String(50), nullable=False, default="staging")

    services_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    environments_json: Mapped[str] = mapped_column(
        Text, default='["staging"]', nullable=False
    )

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    risk_level: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)
    approval_policy: Mapped[str] = mapped_column(
        String(64), default="safe_default", nullable=False
    )

    preferred_dev_tool: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    dev_execution_mode: Mapped[str] = mapped_column(
        String(100), default="autonomous_cli", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
