# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance overview and org-scoped audit helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.governance import Organization, OrganizationMembership
from app.services.governance.policies import get_effective_policy
from app.services.trust_audit_constants import ACCESS_PERMISSION_DENIED, ACCESS_PERMISSION_REQUESTED


def _scoped_audit_rows(db: Session, organization_id: str, *, limit: int = 8000) -> list[AuditLog]:
    oid = (organization_id or "").strip()[:64]
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    rows = list(db.scalars(stmt).all())
    return [r for r in rows if (dict(r.metadata_json or {}).get("organization_id")) == oid]


def build_organization_overview(
    db: Session,
    *,
    organization_id: str,
    current_user_id: str,
) -> dict[str, Any]:
    oid = (organization_id or "").strip()[:64]
    org = db.get(Organization, oid)
    if not org:
        return {"error": "organization_not_found"}

    mem = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == oid,
            OrganizationMembership.user_id == (current_user_id or "").strip()[:64],
        )
    )
    if not mem or not mem.enabled:
        return {"error": "not_a_member"}

    members_out = [
        {
            "user_id": m.user_id,
            "role": m.role,
            "enabled": m.enabled,
        }
        for m in db.scalars(
            select(OrganizationMembership).where(OrganizationMembership.organization_id == oid).order_by(
                OrganizationMembership.id.asc()
            )
        ).all()
    ]

    since = datetime.utcnow() - timedelta(hours=24)
    scoped = _scoped_audit_rows(db, oid)
    events_24h = sum(1 for r in scoped if r.created_at and r.created_at >= since)
    permission_requests = sum(
        1
        for r in scoped
        if r.created_at and r.created_at >= since and (r.event_type or "") == ACCESS_PERMISSION_REQUESTED
    )
    denied_actions = sum(
        1
        for r in scoped
        if r.created_at and r.created_at >= since and (r.event_type or "") == ACCESS_PERMISSION_DENIED
    )

    recent = []
    for r in scoped[:50]:
        recent.append(
            {
                "id": r.id,
                "event_type": r.event_type,
                "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
                "message": (r.message or "")[:300],
                "metadata": dict(r.metadata_json or {}),
            }
        )

    pol = get_effective_policy(db, organization_id=oid)

    return {
        "organization": {"id": org.id, "name": org.name, "enabled": org.enabled},
        "current_user_role": (mem.role or "").strip().lower(),
        "members": members_out,
        "audit_summary": {
            "events_24h": events_24h,
            "permission_requests": permission_requests,
            "denied_actions": denied_actions,
        },
        "recent_events": recent,
        "policies": pol,
    }


def audit_rows_filtered_export(db: Session, organization_id: str, *, limit: int = 10_000) -> list[AuditLog]:
    return _scoped_audit_rows(db, organization_id, limit=limit)
