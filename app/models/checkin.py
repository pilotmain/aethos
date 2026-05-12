# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class CheckIn(Base, TimestampMixin):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", nullable=False)
