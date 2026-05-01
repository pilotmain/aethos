from __future__ import annotations

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


def _default_allowed_tools() -> list:
    return []


def _default_system_prompt() -> str:
    return ""


class AgentDefinition(Base, TimestampMixin):
    __tablename__ = "agent_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default=_default_system_prompt, nullable=False)
    allowed_tools: Mapped[list] = mapped_column(JSON, default=_default_allowed_tools, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
