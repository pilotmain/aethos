"""
Organization management service (Phase 29).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.rbac.models import (
    Invite,
    InviteStatus,
    Organization,
    OrganizationMember,
    RoleType,
    Team,
    TeamMember,
    slugify_name,
)

logger = logging.getLogger(__name__)


class OrganizationService:
    """Manage organizations, members, invites, and teams (SQLite under NEXA_DATA_DIR/rbac.db)."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            settings = get_settings()
            base = Path(getattr(settings, "nexa_data_dir", None) or "data")
            self.db_path = base / "rbac.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    settings TEXT,
                    is_active INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS org_members (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    role TEXT NOT NULL,
                    joined_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    invited_by TEXT,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE (organization_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS invites (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    email TEXT,
                    user_id TEXT,
                    invited_by TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS teams (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS team_members (
                    id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    org_member_id TEXT NOT NULL,
                    joined_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE (team_id, org_member_id)
                );
                CREATE TABLE IF NOT EXISTS user_active_org (
                    user_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_members_org ON org_members(organization_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_invites_org ON invites(organization_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(organization_id)")

    # --- active workspace per user (Telegram id string, etc.) ---

    def get_active_organization_id(self, user_id: str) -> str | None:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT org_id FROM user_active_org WHERE user_id = ?", (user_id,)
            )
            row = cur.fetchone()
        return str(row["org_id"]) if row else None

    def set_active_organization_id(self, user_id: str, org_id: str) -> bool:
        if not self.get_member(org_id, user_id):
            return False
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_active_org (user_id, org_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET org_id = excluded.org_id,
                    updated_at = excluded.updated_at
                """,
                (user_id, org_id, now),
            )
        return True

    # --- organizations ---

    def create_organization(self, name: str, slug: str | None, created_by: str) -> Organization:
        base_slug = slugify_name(slug or name)
        org = Organization.create(name=name.strip(), slug=base_slug, created_by=created_by)
        for attempt in range(12):
            try:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO organizations
                        (id, name, slug, created_by, created_at, updated_at, settings, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        """,
                        (
                            org.id,
                            org.name,
                            org.slug,
                            org.created_by,
                            org.created_at.isoformat(),
                            org.updated_at.isoformat(),
                            json.dumps(org.settings),
                        ),
                    )
                break
            except sqlite3.IntegrityError:
                org.slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
        else:
            raise RuntimeError("Could not allocate unique organization slug")

        m = OrganizationMember.create(org.id, created_by, RoleType.OWNER, invited_by=created_by)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO org_members
                (id, organization_id, user_id, user_name, role, joined_at, updated_at, invited_by, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    m.id,
                    m.organization_id,
                    m.user_id,
                    m.user_name,
                    m.role.value,
                    m.joined_at.isoformat(),
                    m.updated_at.isoformat(),
                    m.invited_by,
                ),
            )
        self.set_active_organization_id(created_by, org.id)
        logger.info("Created organization %s (%s)", org.id, org.slug)
        return org

    def get_organization(self, org_id: str) -> Organization | None:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM organizations WHERE id = ? AND is_active = 1", (org_id,)
            )
            row = cur.fetchone()
        return self._row_to_org(row) if row else None

    def get_organization_by_slug(self, slug: str) -> Organization | None:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM organizations WHERE slug = ? AND is_active = 1",
                (slug.strip().lower(),),
            )
            row = cur.fetchone()
        return self._row_to_org(row) if row else None

    def list_organizations_for_user(self, user_id: str) -> list[Organization]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT o.* FROM organizations o
                JOIN org_members om ON o.id = om.organization_id
                WHERE om.user_id = ? AND om.is_active = 1 AND o.is_active = 1
                ORDER BY o.name COLLATE NOCASE
                """,
                (user_id,),
            )
            return [self._row_to_org(r) for r in cur.fetchall()]

    def update_organization(
        self,
        org_id: str,
        *,
        name: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        org = self.get_organization(org_id)
        if not org:
            return False
        if name:
            org.name = name.strip()
        if settings:
            org.settings.update(settings)
        org.updated_at = datetime.now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE organizations SET name = ?, updated_at = ?, settings = ?
                WHERE id = ?
                """,
                (
                    org.name,
                    org.updated_at.isoformat(),
                    json.dumps(org.settings),
                    org_id,
                ),
            )
        return True

    # --- members ---

    def add_member(
        self,
        org_id: str,
        user_id: str,
        role: RoleType = RoleType.MEMBER,
        user_name: str | None = None,
        invited_by: str | None = None,
    ) -> OrganizationMember | None:
        if self.get_member(org_id, user_id):
            logger.warning("User %s already in organization %s", user_id, org_id)
            return None
        member = OrganizationMember.create(org_id, user_id, role, invited_by)
        member.user_name = user_name
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO org_members
                (id, organization_id, user_id, user_name, role, joined_at, updated_at, invited_by, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    member.id,
                    member.organization_id,
                    member.user_id,
                    member.user_name,
                    member.role.value,
                    member.joined_at.isoformat(),
                    member.updated_at.isoformat(),
                    member.invited_by,
                ),
            )
        logger.info("Added member %s to org %s as %s", user_id, org_id, role.value)
        return member

    def get_member(self, org_id: str, user_id: str) -> OrganizationMember | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM org_members
                WHERE organization_id = ? AND user_id = ? AND is_active = 1
                """,
                (org_id, user_id),
            )
            row = cur.fetchone()
        return self._row_to_member(row) if row else None

    def list_members(self, org_id: str) -> list[OrganizationMember]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM org_members
                WHERE organization_id = ? AND is_active = 1
                ORDER BY joined_at
                """,
                (org_id,),
            )
            return [self._row_to_member(r) for r in cur.fetchall()]

    def update_member_role(self, org_id: str, user_id: str, new_role: RoleType) -> bool:
        member = self.get_member(org_id, user_id)
        if not member:
            return False
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE org_members SET role = ?, updated_at = ?
                WHERE organization_id = ? AND user_id = ?
                """,
                (new_role.value, now, org_id, user_id),
            )
        return True

    def remove_member(self, org_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE org_members SET is_active = 0, updated_at = ?
                WHERE organization_id = ? AND user_id = ?
                """,
                (datetime.now().isoformat(), org_id, user_id),
            )
        return True

    def check_permission(self, org_id: str, user_id: str, permission: str) -> bool:
        member = self.get_member(org_id, user_id)
        if not member:
            return False
        return member.can(permission)

    # --- invites ---

    def create_invite(
        self,
        org_id: str,
        invited_by: str,
        *,
        role: RoleType = RoleType.MEMBER,
        email: str | None = None,
        user_id: str | None = None,
        expires_days: int = 7,
    ) -> Invite | None:
        invite = Invite.create(
            org_id,
            invited_by,
            role=role,
            email=email,
            user_id=user_id,
            expires_days=expires_days,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO invites
                (id, organization_id, email, user_id, invited_by, role, status, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invite.id,
                    invite.organization_id,
                    invite.email,
                    invite.user_id,
                    invite.invited_by,
                    invite.role.value,
                    invite.status.value,
                    invite.expires_at.isoformat(),
                    invite.created_at.isoformat(),
                ),
            )
        return invite

    def get_invite(self, invite_id: str) -> Invite | None:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM invites WHERE id = ?", (invite_id,))
            row = cur.fetchone()
        return self._row_to_invite(row) if row else None

    def accept_invite(
        self, invite_id: str, user_id: str, user_name: str | None = None
    ) -> bool:
        invite = self.get_invite(invite_id)
        if not invite or invite.status != InviteStatus.PENDING:
            return False
        if invite.is_expired():
            with self._connect() as conn:
                conn.execute(
                    "UPDATE invites SET status = ? WHERE id = ?",
                    (InviteStatus.EXPIRED.value, invite_id),
                )
            return False
        member = self.add_member(
            invite.organization_id,
            user_id,
            invite.role,
            user_name=user_name,
            invited_by=invite.invited_by,
        )
        if not member:
            return False
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE invites SET status = ?, user_id = ?
                WHERE id = ?
                """,
                (InviteStatus.ACCEPTED.value, user_id, invite_id),
            )
        return True

    # --- teams ---

    def create_team(
        self,
        org_id: str,
        name: str,
        created_by: str,
        description: str | None = None,
    ) -> Team:
        team = Team.create(org_id, name.strip(), created_by, description)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO teams
                (id, organization_id, name, description, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team.id,
                    team.organization_id,
                    team.name,
                    team.description,
                    team.created_by,
                    team.created_at.isoformat(),
                    team.updated_at.isoformat(),
                ),
            )
        return team

    def list_teams(self, org_id: str) -> list[Team]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM teams WHERE organization_id = ? ORDER BY name COLLATE NOCASE",
                (org_id,),
            )
            return [self._row_to_team(r) for r in cur.fetchall()]

    def add_team_member(self, team_id: str, org_member_id: str) -> bool:
        tid = str(uuid.uuid4())[:10]
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO team_members (id, team_id, org_member_id, joined_at, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (tid, team_id, org_member_id, datetime.now().isoformat()),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def _row_to_org(self, row: sqlite3.Row) -> Organization:
        return Organization(
            id=str(row["id"]),
            name=str(row["name"]),
            slug=str(row["slug"]),
            created_by=str(row["created_by"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            settings=json.loads(row["settings"]) if row["settings"] else {},
            is_active=bool(row["is_active"]),
        )

    def _row_to_member(self, row: sqlite3.Row) -> OrganizationMember:
        return OrganizationMember(
            id=str(row["id"]),
            organization_id=str(row["organization_id"]),
            user_id=str(row["user_id"]),
            user_name=row["user_name"],
            role=RoleType(str(row["role"])),
            joined_at=datetime.fromisoformat(str(row["joined_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            invited_by=row["invited_by"],
            is_active=bool(row["is_active"]),
        )

    def _row_to_invite(self, row: sqlite3.Row) -> Invite:
        return Invite(
            id=str(row["id"]),
            organization_id=str(row["organization_id"]),
            email=row["email"],
            user_id=row["user_id"],
            invited_by=str(row["invited_by"]),
            role=RoleType(str(row["role"])),
            status=InviteStatus(str(row["status"])),
            expires_at=datetime.fromisoformat(str(row["expires_at"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def _row_to_team(self, row: sqlite3.Row) -> Team:
        return Team(
            id=str(row["id"]),
            organization_id=str(row["organization_id"]),
            name=str(row["name"]),
            description=row["description"],
            created_by=str(row["created_by"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )


__all__ = ["OrganizationService"]
