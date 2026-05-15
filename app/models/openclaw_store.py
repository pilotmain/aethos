# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Durable consent grants and activity ledger (OpenClaw-style governance)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NexaConsentGrant(Base):
    __tablename__ = "nexa_consent_grants"

    consent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    grant_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="once")
    granted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NexaActivityLedgerEvent(Base):
    __tablename__ = "nexa_activity_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    payload_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["NexaActivityLedgerEvent", "NexaConsentGrant"]
