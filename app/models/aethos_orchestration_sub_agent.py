"""Persisted orchestration sub-agents (API / Telegram registry scope)."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AethosOrchestrationSubAgent(Base):
    """Rows mirror :class:`~app.services.sub_agent_registry.SubAgent` (process cache)."""

    __tablename__ = "aethos_orchestration_sub_agents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_chat_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_active: Mapped[float] = mapped_column(Float, nullable=False)
    agent_metadata: Mapped[dict] = mapped_column("agent_metadata", JSON, nullable=False, default=dict)
