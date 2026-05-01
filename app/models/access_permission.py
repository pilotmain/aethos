"""Scoped access grants for local tools (permissioned computer access)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class AccessPermission(Base, TimestampMixin):
    """
    Owner-scoped permission row.

    status: pending | granted | revoked | denied | consumed
    target: normalized absolute path (directory) or symbolic target for non-path scopes.
    """

    __tablename__ = "access_permissions"
    __table_args__ = (Index("ix_access_perm_owner_status", "owner_user_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    granted_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
