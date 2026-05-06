"""Phase 51 — AethOS Cloud billing tables (Stripe); keyed by governance :class:`~app.models.governance.Organization`."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class CloudOrgBilling(Base, TimestampMixin):
    """One row per governance organization: Stripe customer + subscription snapshot."""

    __tablename__ = "aethos_cloud_org_billing"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    subscription_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    subscription_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class CloudSaaSCredential(Base, TimestampMixin):
    """Bcrypt password for cloud-registered users (optional; other channels may have no row)."""

    __tablename__ = "aethos_cloud_saas_credentials"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
