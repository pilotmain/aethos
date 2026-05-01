"""Per-organization channel enablement and roles (Phase 13)."""

from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class OrganizationChannelPolicy(Base, TimestampMixin):
    """Which channels are enabled for an enterprise org and which roles may use them."""

    __tablename__ = "organization_channel_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "channel", name="uq_org_channel_policy"),
        Index("ix_ocp_org", "organization_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_roles: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
