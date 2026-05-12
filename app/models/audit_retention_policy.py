# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Organization audit log retention (Phase 13; storage only — no deletion worker in v1)."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class AuditRetentionPolicy(Base, TimestampMixin):
    __tablename__ = "audit_retention_policies"

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
