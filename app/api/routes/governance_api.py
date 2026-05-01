"""Enterprise governance — organizations, policies, retention (Phase 13+)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.audit_log import AuditLog
from app.models.audit_retention_policy import AuditRetentionPolicy
from app.models.governance import OrganizationMembership, OrganizationPolicy
from app.models.organization_channel_policy import OrganizationChannelPolicy
from app.models.user import User
from app.schemas.governance import (
    MemberCreateIn,
    MemberPatchIn,
    OrganizationCreateIn,
    OrganizationOut,
    OrganizationPolicyPatchIn,
)
from app.services.audit_service import audit
from app.services.channel_gateway.governance import ALL_GOVERNANCE_ROLES, merge_channel_status_governance
from app.services.channel_gateway.status import build_channel_status_list
from app.services.governance.read_model import audit_rows_filtered_export, build_organization_overview
from app.services.governance.service import (
    ROLE_ADMIN,
    ROLE_AUDITOR,
    ROLE_MEMBER,
    ROLE_OWNER,
    ROLE_VIEWER,
    _EXPORT_ROLES,
    _MANAGE_ROLES,
    add_member,
    create_organization,
    ensure_default_organization,
    get_organization,
    list_organizations_for_user,
    require_org_role,
)

_ANY_MEMBER_ROLES = frozenset({ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER, ROLE_AUDITOR, ROLE_VIEWER})
from app.services.governance.policies import get_effective_policy
from app.services.governance_taxonomy import EVENT_CHANNEL_POLICY_UPDATED, EVENT_RETENTION_POLICY_UPDATED

router = APIRouter(prefix="/governance", tags=["governance"])


def _require_governance_feature_enabled() -> None:
    if not get_settings().nexa_governance_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Governance is disabled. Set NEXA_GOVERNANCE_ENABLED=true on the API.",
        )


def _require_admin_role(db: Session, user_id: str) -> None:
    if not get_settings().nexa_governance_enabled:
        return
    u = db.get(User, user_id)
    role = str((u.governance_role if u else "") or "").strip().lower()
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner or admin role required")


class RetentionPatch(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    retention_days: int = Field(ge=1, le=3650, default=365)


class ChannelPolicyPatch(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    channel: str = Field(min_length=1, max_length=32)
    enabled: bool = True
    allowed_roles: list[str] = Field(default_factory=list)
    approval_required: bool = False


@router.get("/overview")
def governance_overview(
    organization_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Policies + retention + channel status snapshot for an org (admin UI)."""
    _require_admin_role(db, app_user_id)
    oid = organization_id.strip()
    ret = db.get(AuditRetentionPolicy, oid)
    retention_days = int(ret.retention_days) if ret else 365
    policies = db.scalars(select(OrganizationChannelPolicy).where(OrganizationChannelPolicy.organization_id == oid)).all()
    policy_rows = [
        {
            "channel": p.channel,
            "enabled": p.enabled,
            "allowed_roles": list(p.allowed_roles or []),
            "approval_required": p.approval_required,
        }
        for p in policies
    ]
    rows = build_channel_status_list()
    rows = merge_channel_status_governance(db, rows, organization_id=oid)
    return {
        "organization_id": oid,
        "retention_days": retention_days,
        "policies": policy_rows,
        "channels": rows,
    }


@router.patch("/retention")
def patch_retention(
    body: RetentionPatch,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_admin_role(db, app_user_id)
    row = db.get(AuditRetentionPolicy, body.organization_id.strip())
    if not row:
        row = AuditRetentionPolicy(organization_id=body.organization_id.strip(), retention_days=body.retention_days)
        db.add(row)
    else:
        row.retention_days = body.retention_days
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type=EVENT_RETENTION_POLICY_UPDATED,
        actor="governance",
        user_id=app_user_id,
        message=f"retention org={row.organization_id} days={row.retention_days}",
        metadata={"organization_id": row.organization_id, "retention_days": row.retention_days},
    )
    return {"ok": True, "organization_id": row.organization_id, "retention_days": row.retention_days}


@router.patch("/channel-policy")
def patch_channel_policy(
    body: ChannelPolicyPatch,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_admin_role(db, app_user_id)
    oid = body.organization_id.strip()
    ch = body.channel.strip().lower()
    roles = [str(x).strip().lower() for x in (body.allowed_roles or []) if str(x).strip()]
    if not roles:
        roles = list(ALL_GOVERNANCE_ROLES)
    existing = db.scalar(
        select(OrganizationChannelPolicy).where(
            OrganizationChannelPolicy.organization_id == oid,
            OrganizationChannelPolicy.channel == ch,
        )
    )
    if existing:
        existing.enabled = body.enabled
        existing.allowed_roles = roles
        existing.approval_required = body.approval_required
        db.add(existing)
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = OrganizationChannelPolicy(
            organization_id=oid,
            channel=ch,
            enabled=body.enabled,
            allowed_roles=roles,
            approval_required=body.approval_required,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    audit(
        db,
        event_type=EVENT_CHANNEL_POLICY_UPDATED,
        actor="governance",
        user_id=app_user_id,
        message=f"channel_policy org={oid} channel={ch}",
        metadata={
            "organization_id": oid,
            "channel": ch,
            "enabled": row.enabled,
            "allowed_roles": roles,
            "approval_required": row.approval_required,
        },
    )
    return {
        "ok": True,
        "organization_id": oid,
        "channel": ch,
        "enabled": row.enabled,
        "allowed_roles": roles,
        "approval_required": row.approval_required,
    }


# --- Governance organizations (database-backed) ---


@router.get("/me")
def governance_me(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Feature flag + org list for the current user."""
    s = get_settings()
    if not s.nexa_governance_enabled:
        return {
            "governance_enabled": False,
            "default_organization_id": None,
            "organizations": [],
        }
    ensure_default_organization(db, user_id=app_user_id)
    orgs = list_organizations_for_user(db, user_id=app_user_id)
    return {
        "governance_enabled": True,
        "default_organization_id": s.nexa_default_organization_id,
        "organizations": [{"id": o.id, "name": o.name, "enabled": o.enabled} for o in orgs],
    }


@router.get("/organizations")
def list_governance_organizations(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_governance_feature_enabled()
    ensure_default_organization(db, user_id=app_user_id)
    orgs = list_organizations_for_user(db, user_id=app_user_id)
    return {
        "organizations": [
            OrganizationOut(id=o.id, name=o.name, owner_user_id=o.owner_user_id, enabled=o.enabled) for o in orgs
        ]
    }


@router.post("/organizations", response_model=OrganizationOut)
def post_governance_organization(
    body: OrganizationCreateIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> OrganizationOut:
    _require_governance_feature_enabled()
    org = create_organization(
        db,
        organization_id=body.id,
        name=body.name,
        owner_user_id=app_user_id,
    )
    return OrganizationOut(id=org.id, name=org.name, owner_user_id=org.owner_user_id, enabled=org.enabled)


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
def get_governance_organization(
    org_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> OrganizationOut:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_ANY_MEMBER_ROLES)
    org = get_organization(db, organization_id=org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return OrganizationOut(id=org.id, name=org.name, owner_user_id=org.owner_user_id, enabled=org.enabled)


@router.get("/organizations/{org_id}/members")
def list_org_members(
    org_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_ANY_MEMBER_ROLES)
    rows = list(
        db.scalars(
            select(OrganizationMembership).where(OrganizationMembership.organization_id == org_id.strip()[:64])
        ).all()
    )
    return {
        "members": [{"user_id": r.user_id, "role": r.role, "enabled": r.enabled} for r in rows],
    }


@router.post("/organizations/{org_id}/members")
def post_org_member(
    org_id: str,
    body: MemberCreateIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_MANAGE_ROLES)
    row = add_member(db, organization_id=org_id, user_id=body.user_id, role=body.role)
    audit(
        db,
        event_type="governance.membership.updated",
        actor="governance",
        user_id=app_user_id,
        message=f"member {row.user_id} role={row.role} org={org_id}",
        metadata={"organization_id": org_id.strip()[:64], "target_user_id": row.user_id},
        organization_id=org_id.strip()[:64],
    )
    return {"ok": True, "user_id": row.user_id, "role": row.role, "enabled": row.enabled}


@router.patch("/organizations/{org_id}/members/{member_user_id}")
def patch_org_member(
    org_id: str,
    member_user_id: str,
    body: MemberPatchIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_MANAGE_ROLES)
    m = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id.strip()[:64],
            OrganizationMembership.user_id == member_user_id.strip()[:64],
        )
    )
    if not m:
        raise HTTPException(status_code=404, detail="Membership not found.")
    if body.role is not None:
        m.role = body.role.strip()[:32]
    if body.enabled is not None:
        m.enabled = bool(body.enabled)
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"ok": True, "user_id": m.user_id, "role": m.role, "enabled": m.enabled}


@router.get("/organizations/{org_id}/policies")
def get_org_policies(
    org_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_ANY_MEMBER_ROLES)
    return {"effective": get_effective_policy(db, organization_id=org_id.strip()[:64])}


@router.patch("/organizations/{org_id}/policies")
def patch_org_policies(
    org_id: str,
    body: OrganizationPolicyPatchIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_MANAGE_ROLES)
    oid = org_id.strip()[:64]
    row = db.scalar(
        select(OrganizationPolicy).where(
            OrganizationPolicy.organization_id == oid,
            OrganizationPolicy.policy_key == "default",
        )
    )
    base: dict[str, Any] = dict(row.policy_json or {}) if row else {}
    merged = {**base, **(body.policy_json or {})}
    if row:
        row.policy_json = merged
        row.enabled = True
        db.add(row)
    else:
        db.add(
            OrganizationPolicy(
                organization_id=oid,
                policy_key="default",
                policy_json=merged,
                enabled=True,
            )
        )
    db.commit()
    audit(
        db,
        event_type="governance.policy.updated",
        actor="governance",
        user_id=app_user_id,
        message=f"policy org={oid}",
        metadata={"organization_id": oid},
        organization_id=oid,
    )
    return {"ok": True, "effective": get_effective_policy(db, organization_id=oid)}


@router.get("/organizations/{org_id}/overview")
def org_overview(
    org_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _require_governance_feature_enabled()
    out = build_organization_overview(db, organization_id=org_id, current_user_id=app_user_id)
    err = out.get("error")
    if err == "organization_not_found":
        raise HTTPException(status_code=404, detail="Organization not found.")
    if err == "not_a_member":
        raise HTTPException(status_code=403, detail="You are not a member of this organization.")
    return out


def _audit_export_rows(org_rows: list[AuditLog], *, format: str) -> Response:
    def row_dict(r: AuditLog) -> dict[str, object]:
        md = dict(r.metadata_json or {})
        return {
            "id": r.id,
            "timestamp": r.created_at.isoformat() if r.created_at else "",
            "user_id": r.user_id,
            "event_type": r.event_type,
            "actor": r.actor,
            "message": (r.message or "")[:500],
            "metadata": md,
        }

    out_rows = [row_dict(r) for r in org_rows]
    if format == "json":
        return Response(
            content=json.dumps({"events": out_rows}, indent=2, default=str),
            media_type="application/json",
        )
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "timestamp", "user_id", "event_type", "actor", "message", "metadata"])
    w.writeheader()
    for row in out_rows:
        w.writerow({k: json.dumps(v) if k == "metadata" else v for k, v in row.items()})
    return Response(content=buf.getvalue(), media_type="text/csv")


@router.get("/organizations/{org_id}/audit/export.json")
def export_org_audit_json(
    org_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> Response:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_EXPORT_ROLES)
    rows = audit_rows_filtered_export(db, org_id.strip()[:64])
    audit(
        db,
        event_type="governance.audit_export",
        actor="governance",
        user_id=app_user_id,
        message=f"org audit export json org={org_id}",
        metadata={"organization_id": org_id.strip()[:64], "format": "json", "rows": len(rows)},
        organization_id=org_id.strip()[:64],
    )
    return _audit_export_rows(rows, format="json")


@router.get("/organizations/{org_id}/audit/export.csv")
def export_org_audit_csv(
    org_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> Response:
    _require_governance_feature_enabled()
    require_org_role(db, organization_id=org_id, user_id=app_user_id, allowed_roles=_EXPORT_ROLES)
    rows = audit_rows_filtered_export(db, org_id.strip()[:64])
    audit(
        db,
        event_type="governance.audit_export",
        actor="governance",
        user_id=app_user_id,
        message=f"org audit export csv org={org_id}",
        metadata={"organization_id": org_id.strip()[:64], "format": "csv", "rows": len(rows)},
        organization_id=org_id.strip()[:64],
    )
    return _audit_export_rows(rows, format="csv")
