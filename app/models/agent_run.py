from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


def _default_plan() -> dict:
    return {}


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="queued", index=True, nullable=False
    )  # queued | planning | waiting_approval | executing | completed | failed | blocked
    plan_json: Mapped[dict] = mapped_column(JSON, default=_default_plan, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    related_agent_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
