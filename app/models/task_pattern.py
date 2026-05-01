import uuid

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class TaskPattern(Base, TimestampMixin):
    __tablename__ = "task_patterns"
    __table_args__ = (UniqueConstraint("user_id", "task_title", name="uq_task_patterns_user_task"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task_title: Mapped[str] = mapped_column(Text, nullable=False)
    times_attempted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
