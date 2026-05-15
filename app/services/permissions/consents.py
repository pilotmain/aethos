# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tool/skill consent records (mobile-style permission grants)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.openclaw_store import NexaConsentGrant

GrantMode = Literal["once", "session", "until_revoked"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ConsentRecord:
    consent_id: str
    scope: str
    resource: str
    granted_until: datetime | None
    grant_mode: GrantMode
    revoked_at: datetime | None = None
    reason: str | None = None


def _row_to_record(row: NexaConsentGrant) -> ConsentRecord:
    return ConsentRecord(
        consent_id=row.consent_id,
        scope=row.scope,
        resource=row.resource,
        granted_until=row.granted_until,
        grant_mode=row.grant_mode,  # type: ignore[arg-type]
        revoked_at=row.revoked_at,
        reason=row.reason,
    )


def request_consent(
    *,
    scope: str,
    resource: str,
    grant_mode: GrantMode = "once",
    granted_until: datetime | None = None,
) -> ConsentRecord:
    cid = str(uuid4())
    return ConsentRecord(
        consent_id=cid,
        scope=scope[:256],
        resource=resource[:512],
        granted_until=granted_until,
        grant_mode=grant_mode,
    )


def grant_consent(rec: ConsentRecord) -> ConsentRecord:
    db = SessionLocal()
    try:
        row = NexaConsentGrant(
            consent_id=rec.consent_id,
            scope=rec.scope,
            resource=rec.resource,
            grant_mode=rec.grant_mode,
            granted_until=rec.granted_until,
            revoked_at=rec.revoked_at,
            reason=rec.reason,
            created_at=_utc_now(),
        )
        db.add(row)
        db.commit()
        return rec
    finally:
        db.close()


def revoke_consent(consent_id: str, *, reason: str | None = None) -> ConsentRecord | None:
    db = SessionLocal()
    try:
        row = db.get(NexaConsentGrant, consent_id)
        if not row:
            return None
        row.revoked_at = _utc_now()
        row.reason = (reason or "")[:500] or None
        db.add(row)
        db.commit()
        return _row_to_record(row)
    finally:
        db.close()


def check_consent(*, scope: str, resource: str, at: datetime | None = None) -> bool:
    now = at or _utc_now()
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(NexaConsentGrant).where(
                NexaConsentGrant.scope == scope,
                NexaConsentGrant.resource == resource,
            )
        ).all()
        for row in rows:
            if row.revoked_at is not None:
                continue
            if row.granted_until is not None and row.granted_until < now:
                continue
            return True
        return False
    finally:
        db.close()


def reset_consents_for_tests() -> None:
    db = SessionLocal()
    try:
        for row in db.scalars(select(NexaConsentGrant)).all():
            db.delete(row)
        db.commit()
    finally:
        db.close()


__all__ = [
    "ConsentRecord",
    "check_consent",
    "grant_consent",
    "request_consent",
    "reset_consents_for_tests",
    "revoke_consent",
]
