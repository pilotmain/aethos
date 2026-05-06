from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class ConversationContext(Base, TimestampMixin):
    """Per-user rolling conversation state for cross-turn references (not long-term memory)."""

    __tablename__ = "conversation_contexts"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_cc_user_session"),
        Index("ix_conversation_contexts_user_session", "user_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # "default" = legacy single-thread (Telegram + first web tab); new web chats use a unique id
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    # Web sidebar title (Telegram can ignore)
    web_chat_title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Nexa workspace project (labeled folder); distinct from Ops ``active_project`` key above.
    active_project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("aethos_workspace_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    active_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recent_messages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    last_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_agent_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Topic authority (vNext)
    active_topic_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    last_topic_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    manual_topic_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Idea-to-project (draft from chat before Project row exists)
    pending_project_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Last user-safe decision (JSON); no prompts or private reasoning
    last_decision_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Co-pilot: last "Next steps" block (JSON list of {index, label, command, risk, created_at})
    last_suggested_actions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # One-line command awaiting "run" (unknown / non-prefixed suggestions)
    next_action_pending_inject_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Last command successfully injected from a next-step or repeat ("do it again")
    last_injected_action_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lightweight co-pilot flow: goal, steps, last_action, timestamps (chat-only, no background runs)
    current_flow_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Host action waiting for access grant (JSON: payload, title, permission_id)
    blocked_host_executor_json: Mapped[str | None] = mapped_column(Text, nullable=True)
