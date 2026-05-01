"""User-defined Nexa workspace projects — folders inside approved workspace roots.

Not to be confused with ``Project`` (Ops/cloud registry). Each row is a labeled path
within the user's registered workspace + host executor work tree for context switching.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class NexaWorkspaceProject(Base, TimestampMixin):
    """
    A named folder the user treats as their current Nexa project.

    ``path_normalized`` must lie under registered workspace roots and under the
    configured host executor work root (validated at insert).
    """

    __tablename__ = "nexa_workspace_projects"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "path_normalized", name="uq_nexa_ws_proj_owner_path"),
        Index("ix_nexa_ws_proj_owner", "owner_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    path_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
