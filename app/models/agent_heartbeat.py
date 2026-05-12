# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AgentHeartbeat(Base):
    __tablename__ = "agent_heartbeats"
    __table_args__ = (UniqueConstraint("user_id", "agent_key", name="uq_heartbeat_user_agent"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)  # idle | running | blocked | failed
    current_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=func.now(), onupdate=func.now(), nullable=False
    )
