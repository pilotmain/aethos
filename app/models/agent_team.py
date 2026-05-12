# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Durable agent organization, roles, and assignments (orchestration layer V1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class AgentOrganization(Base, TimestampMixin):
    """One logical team per user (V1: single default org per user)."""

    __tablename__ = "agent_organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Optional link to governance `organizations.id` (string org container).
    governance_organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    roles: Mapped[list["AgentRoleAssignment"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["AgentAssignment"]] = relationship(
        back_populates="organization",
    )


class AgentRoleAssignment(Base, TimestampMixin):
    """Role + hierarchy metadata for a handle within an organization."""

    __tablename__ = "agent_role_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agent_organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_handle: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    reports_to_handle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skills_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    responsibilities_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["AgentOrganization"] = relationship(back_populates="roles")


class AgentAssignment(Base, TimestampMixin):
    """Single unit of orchestrated work; always has a durable id before async claims."""

    __tablename__ = "agent_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_assignment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_assignments.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_handle: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    assigned_by_handle: Mapped[str] = mapped_column(String(64), nullable=False, default="orchestrator")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="queued")
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    channel_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    web_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    organization: Mapped["AgentOrganization | None"] = relationship(
        back_populates="assignments",
        foreign_keys=[organization_id],
    )


# TimestampMixin provides created_at / updated_at; ensure AgentAssignment has explicit lifecycle columns
# (started_at / completed_at) for orchestration UX.
