import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class BrainDump(Base, TimestampMixin):
    __tablename__ = "brain_dumps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_source: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    emotional_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
