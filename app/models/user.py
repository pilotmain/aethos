# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York", nullable=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Focus / loop tracking (nudge & unstick personalization)
    last_focus_task: Mapped[str | None] = mapped_column(Text, nullable=True)
    focus_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    # Phase 13 — enterprise governance (optional; unset = personal/single-tenant behavior)
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    governance_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
