# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tool/skill consent records (mobile-style permission grants)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

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


_STORE: dict[str, ConsentRecord] = {}


def request_consent(
    *,
    scope: str,
    resource: str,
    grant_mode: GrantMode = "once",
    granted_until: datetime | None = None,
) -> ConsentRecord:
    cid = str(uuid4())
    rec = ConsentRecord(
        consent_id=cid,
        scope=scope[:256],
        resource=resource[:512],
        granted_until=granted_until,
        grant_mode=grant_mode,
    )
    return rec


def grant_consent(rec: ConsentRecord) -> ConsentRecord:
    _STORE[rec.consent_id] = rec
    return rec


def revoke_consent(consent_id: str, *, reason: str | None = None) -> ConsentRecord | None:
    rec = _STORE.get(consent_id)
    if not rec:
        return None
    rec.revoked_at = _utc_now()
    rec.reason = (reason or "")[:500] or None
    return rec


def check_consent(*, scope: str, resource: str, at: datetime | None = None) -> bool:
    now = at or _utc_now()
    for rec in _STORE.values():
        if rec.revoked_at is not None:
            continue
        if rec.scope != scope or rec.resource != resource:
            continue
        if rec.granted_until is not None and rec.granted_until < now:
            continue
        return True
    return False


__all__ = [
    "ConsentRecord",
    "check_consent",
    "grant_consent",
    "request_consent",
    "revoke_consent",
]
