# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Registered safe filesystem roots per owner (workspace registry)."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class WorkspaceRoot(Base, TimestampMixin):
    """An absolute directory the owner allowed Nexa to treat as a workspace boundary."""

    __tablename__ = "workspace_roots"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "path_normalized", name="uq_workspace_owner_path"),
        Index("ix_workspace_roots_owner", "owner_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    path_normalized: Mapped[str] = mapped_column(String(1024), nullable=False)
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
