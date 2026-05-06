"""Cloud SaaS registration and login (email + password, JWT bearer)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.cloud_saas import require_cloud_enabled
from app.core.config import get_settings
from app.core.db import get_db
from app.models.cloud_billing import CloudOrgBilling, CloudSaaSCredential
from app.models.governance import Organization, OrganizationMembership
from app.models.user import User
from app.services.cloud_saas.jwt_tokens import create_cloud_access_token
from app.services.cloud_saas.passwords import hash_password, verify_password

router = APIRouter(prefix="/saas/auth", tags=["saas-auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)


def _nexa_secret_configured() -> None:
    if not (get_settings().nexa_secret_key or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXA_SECRET_KEY is required for cloud authentication",
        )


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    require_cloud_enabled()
    _nexa_secret_configured()
    email_norm = body.email.strip().lower()

    dup = db.execute(
        select(User.id).where(User.email.is_not(None)).where(func.lower(User.email) == email_norm)
    ).first()
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    workspace_name = (body.name.strip() or "Workspace")[:200]
    org_name = f"{workspace_name}'s Workspace"[:200]

    org = Organization(id=org_id, name=org_name, owner_user_id=user_id, enabled=True)
    db.add(org)

    user = User(
        id=user_id,
        name=workspace_name,
        email=email_norm,
        organization_id=org_id,
        governance_role="owner",
    )
    db.add(user)

    db.add(
        OrganizationMembership(
            organization_id=org_id,
            user_id=user_id,
            role="owner",
            enabled=True,
        )
    )
    db.add(CloudSaaSCredential(user_id=user_id, password_hash=hash_password(body.password)))
    db.add(
        CloudOrgBilling(
            organization_id=org_id,
            subscription_tier="free",
            subscription_status="active",
        )
    )

    db.commit()
    db.refresh(user)

    token = create_cloud_access_token(user_id=user.id, email=email_norm, organization_id=org_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": email_norm, "organization_id": org_id},
    }


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    require_cloud_enabled()
    _nexa_secret_configured()
    email_norm = body.email.strip().lower()

    user = db.execute(
        select(User).where(User.email.is_not(None)).where(func.lower(User.email) == email_norm)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    cred = db.get(CloudSaaSCredential, user.id)
    if cred is None or not verify_password(body.password, cred.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.organization_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User has no organization")

    token = create_cloud_access_token(
        user_id=user.id,
        email=email_norm,
        organization_id=user.organization_id,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": email_norm, "organization_id": user.organization_id},
    }
