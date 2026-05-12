# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class LlmUsageEvent(Base, TimestampMixin):
    __tablename__ = "llm_usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    telegram_user_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    source: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="unknown")
    agent_key: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    action_type: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    used_user_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
