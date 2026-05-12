# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Multi-tenant RBAC models (Phase 29).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class RoleType(Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class InviteStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def slugify_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:60] if s else "workspace"


@dataclass
class Organization:
    """Organization (workspace) — top-level isolation boundary."""

    id: str
    name: str
    slug: str
    created_by: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    settings: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    @classmethod
    def create(cls, name: str, slug: str, created_by: str) -> Organization:
        return cls(id=str(uuid.uuid4())[:12], name=name, slug=slug, created_by=created_by)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
        }


@dataclass
class OrganizationMember:
    """Member of an organization with assigned role."""

    id: str
    organization_id: str
    user_id: str
    user_name: str | None = None
    role: RoleType = RoleType.MEMBER
    joined_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    invited_by: str | None = None
    is_active: bool = True

    @classmethod
    def create(
        cls,
        organization_id: str,
        user_id: str,
        role: RoleType = RoleType.MEMBER,
        invited_by: str | None = None,
    ) -> OrganizationMember:
        return cls(
            id=str(uuid.uuid4())[:10],
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
        )

    def can(self, permission: str) -> bool:
        permissions: dict[RoleType, list[str]] = {
            RoleType.OWNER: [
                "manage_org",
                "delete_org",
                "manage_members",
                "manage_roles",
                "manage_billing",
                "manage_settings",
                "create_project",
                "delete_project",
                "manage_tasks",
                "run_agents",
                "view_all",
            ],
            RoleType.ADMIN: [
                "manage_members",
                "manage_settings",
                "create_project",
                "delete_project",
                "manage_tasks",
                "run_agents",
                "view_all",
            ],
            RoleType.MEMBER: ["create_project", "manage_tasks", "run_agents", "view_all"],
            RoleType.VIEWER: ["view_all"],
        }
        return permission in permissions.get(self.role, [])


@dataclass
class Invite:
    """Invitation to join an organization."""

    id: str
    organization_id: str
    invited_by: str
    email: str | None = None
    user_id: str | None = None
    role: RoleType = RoleType.MEMBER
    status: InviteStatus = InviteStatus.PENDING
    expires_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        organization_id: str,
        invited_by: str,
        *,
        role: RoleType = RoleType.MEMBER,
        email: str | None = None,
        user_id: str | None = None,
        expires_days: int = 7,
    ) -> Invite:
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4())[:10],
            organization_id=organization_id,
            invited_by=invited_by,
            email=email,
            user_id=user_id,
            role=role,
            status=InviteStatus.PENDING,
            expires_at=now + timedelta(days=max(1, expires_days)),
            created_at=now,
        )

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


@dataclass
class Team:
    """Team within an organization (sub-group for projects)."""

    id: str
    organization_id: str
    name: str
    created_by: str
    description: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        organization_id: str,
        name: str,
        created_by: str,
        description: str | None = None,
    ) -> Team:
        return cls(
            id=str(uuid.uuid4())[:10],
            organization_id=organization_id,
            name=name,
            created_by=created_by,
            description=description,
        )


@dataclass
class TeamMember:
    """Organization member linked to a team."""

    id: str
    team_id: str
    organization_member_id: str
    joined_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


__all__ = [
    "Invite",
    "InviteStatus",
    "Organization",
    "OrganizationMember",
    "RoleType",
    "Team",
    "TeamMember",
    "slugify_name",
]
