"""Per-user custom agents (chat-created; LLM-only by default)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin

_DEFAULT_TOOLS: str = "[]"
_DEFAULT_SAFETY = "standard"


class UserAgent(Base, TimestampMixin):
    __tablename__ = "user_agents"
    __table_args__ = (
        Index(
            "ix_user_agents_owner_key",
            "owner_user_id",
            "agent_key",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    allowed_tools_json: Mapped[str] = mapped_column(
        Text, nullable=False, default=_DEFAULT_TOOLS
    )
    safety_level: Mapped[str] = mapped_column(String(32), nullable=False, default=_DEFAULT_SAFETY)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def get_allowed_tools(self) -> list[Any]:
        try:
            v = json.loads(self.allowed_tools_json or "[]")
            return v if isinstance(v, list) else []
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    def set_allowed_tools(self, tools: list) -> None:
        self.allowed_tools_json = json.dumps(list(tools or []), default=str)[:20_000]
