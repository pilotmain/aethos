import uuid
from datetime import date

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    source_brain_dump_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="normal", nullable=False)


class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
