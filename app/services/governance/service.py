"""Organizations, memberships, roles (governance layer)."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.governance import Organization, OrganizationMembership, OrganizationPolicy
from app.services.audit_service import audit
from app.services.governance.policies import DEFAULT_EFFECTIVE_POLICY

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_AUDITOR = "auditor"
ROLE_VIEWER = "viewer"

_MANAGE_ROLES = frozenset({ROLE_OWNER, ROLE_ADMIN})
_OVERVIEW_ROLES = frozenset({ROLE_OWNER, ROLE_ADMIN, ROLE_AUDITOR})
_EXPORT_ROLES = frozenset({ROLE_OWNER, ROLE_ADMIN, ROLE_AUDITOR})


def _now_iso_metadata() -> dict[str, Any]:
    return {}


def create_organization(
    db: Session,
    *,
    organization_id: str | None,
    name: str,
    owner_user_id: str,
) -> Organization:
    oid = (organization_id or "").strip()[:64]
    if not oid:
        oid = f"org_{uuid.uuid4().hex[:12]}"
    uid = (owner_user_id or "").strip()[:64]
    existing = db.get(Organization, oid)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization id already exists.")
    org = Organization(id=oid, name=(name or oid)[:200], owner_user_id=uid, enabled=True)
    db.add(org)
    db.flush()
    mem = OrganizationMembership(
        organization_id=oid,
        user_id=uid,
        role=ROLE_OWNER,
        enabled=True,
    )
    db.add(mem)
    pol = OrganizationPolicy(
        organization_id=oid,
        policy_key="default",
        policy_json=dict(DEFAULT_EFFECTIVE_POLICY),
        enabled=True,
    )
    db.add(pol)
    db.commit()
    db.refresh(org)
    audit(
        db,
        event_type="governance.organization.created",
        actor="governance",
        user_id=uid,
        message=f"organization id={oid}",
        metadata={"organization_id": oid},
        organization_id=oid,
    )
    return org


def get_organization(db: Session, *, organization_id: str) -> Organization | None:
    return db.get(Organization, (organization_id or "").strip()[:64])


def list_organizations_for_user(db: Session, *, user_id: str) -> list[Organization]:
    uid = (user_id or "").strip()[:64]
    stmt = (
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == uid, OrganizationMembership.enabled.is_(True), Organization.enabled.is_(True))
        .order_by(Organization.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_membership(db: Session, *, organization_id: str, user_id: str) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == (organization_id or "").strip()[:64],
            OrganizationMembership.user_id == (user_id or "").strip()[:64],
        )
    )


def add_member(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    role: str,
) -> OrganizationMembership:
    oid = (organization_id or "").strip()[:64]
    uid = (user_id or "").strip()[:64]
    r = (role or ROLE_MEMBER).strip().lower()[:32]
    existing = get_membership(db, organization_id=oid, user_id=uid)
    if existing:
        existing.role = r
        existing.enabled = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    row = OrganizationMembership(organization_id=oid, user_id=uid, role=r, enabled=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def require_org_role(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    allowed_roles: frozenset[str],
) -> OrganizationMembership:
    m = get_membership(db, organization_id=organization_id, user_id=user_id)
    if not m or not m.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization.",
        )
    role = (m.role or "").strip().lower()
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this operation.",
        )
    return m


def ensure_default_organization(db: Session, *, user_id: str) -> Organization | None:
    """
    If auto-create is enabled and default org id is set, create org + owner membership when missing.

    Returns the org when created or existing, else None.
    """
    s = get_settings()
    if not s.nexa_governance_enabled or not s.nexa_auto_create_default_org:
        return None
    oid = (s.nexa_default_organization_id or "").strip()[:64]
    if not oid:
        return None
    uid = (user_id or "").strip()[:64]
    org = get_organization(db, organization_id=oid)
    if org:
        if not get_membership(db, organization_id=oid, user_id=uid):
            add_member(db, organization_id=oid, user_id=uid, role=ROLE_OWNER)
        return org
    return create_organization(db, organization_id=oid, name=oid.replace("_", " ").title(), owner_user_id=uid)


def random_org_id() -> str:
    return f"org_{secrets.token_hex(6)}"
