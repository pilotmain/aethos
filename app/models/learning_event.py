# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class LearningEvent(Base, TimestampMixin):
    __tablename__ = "learning_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    agent_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(64), default="observation", nullable=False
    )  # correction | success | failure | preference | repeated_issue
    observation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proposed_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Legacy booleans; prefer `status` (pending | approved | rejected | applied)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False, index=True
    )  # pending | approved | rejected | applied
