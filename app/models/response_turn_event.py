from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class ResponseTurnEvent(Base, TimestampMixin):
    """One row per user message (web or Telegram) for efficiency ratio — no prompts."""

    __tablename__ = "response_turn_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False, default="default")
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    had_llm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
