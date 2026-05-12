# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""FastAPI dependencies for AethOS Cloud (JWT + governance org + billing row)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.cloud_billing import CloudOrgBilling
from app.models.governance import Organization
from app.models.user import User
from app.services.cloud_saas.jwt_tokens import decode_cloud_access_token_payload

_bearer = HTTPBearer(auto_error=False)


def require_cloud_enabled() -> None:
    if not get_settings().aethos_cloud_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AethOS Cloud is disabled (set AETHOS_CLOUD_ENABLED=true)",
        )


@dataclass(frozen=True)
class CloudSaasContext:
    user: User
    organization: Organization
    billing: CloudOrgBilling


def _get_billing(db: Session, organization_id: str) -> CloudOrgBilling | None:
    return db.execute(
        select(CloudOrgBilling).where(CloudOrgBilling.organization_id == organization_id)
    ).scalar_one_or_none()


async def get_cloud_saas_context_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CloudSaasContext | None:
    """Return cloud context if Bearer JWT is valid; otherwise ``None``."""
    require_cloud_enabled()
    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        return None
    token = (credentials.credentials or "").strip()
    if not token:
        return None
    try:
        payload = decode_cloud_access_token_payload(token)
    except Exception:
        return None
    if str(payload.get("typ") or "") != "aethos_cloud":
        return None
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None or not user.organization_id:
        return None
    org = db.get(Organization, user.organization_id)
    if org is None:
        return None
    billing = _get_billing(db, org.id)
    if billing is None:
        return None
    return CloudSaasContext(user=user, organization=org, billing=billing)


async def get_cloud_saas_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CloudSaasContext:
    """Require valid cloud Bearer JWT."""
    require_cloud_enabled()
    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = (credentials.credentials or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_cloud_access_token_payload(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None
    if str(payload.get("typ") or "") != "aethos_cloud":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    user = db.get(User, user_id)
    if user is None or not user.organization_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    org = db.get(Organization, user.organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Organization not found")
    billing = _get_billing(db, org.id)
    if billing is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloud billing profile missing for this organization",
        )
    return CloudSaasContext(user=user, organization=org, billing=billing)


__all__ = [
    "CloudSaasContext",
    "require_cloud_enabled",
    "get_cloud_saas_context",
    "get_cloud_saas_context_optional",
]
