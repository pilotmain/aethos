# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Permission request approve / deny + pending list (API path: /api/v1/permissions/...)."""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.access_permission import AccessPermission
from app.schemas.agent_job import AgentJobRead
from app.schemas.web_ui import WebAccessPermissionOut
from app.services.access_permissions import (
    STATUS_PENDING,
)
from app.services.access_permissions import (
    deny_permission as ap_deny_permission,
)
from app.services.access_permissions import (
    grant_permission as ap_grant_permission,
)
from app.services.agent_job_service import AgentJobService
from app.services.channel_gateway.email_token import verify_email_permission_token
from app.services.permission_resume_execution import PermissionResumeError, resume_host_executor_after_grant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permissions", tags=["permissions"])

job_service = AgentJobService()


def _perm_out(row: AccessPermission) -> WebAccessPermissionOut:
    from app.services.access_permissions import GRANT_MODE_PERSISTENT

    md = dict(row.metadata_json or {})
    gm = (md.get("grant_mode") or GRANT_MODE_PERSISTENT) or GRANT_MODE_PERSISTENT
    return WebAccessPermissionOut(
        id=row.id,
        scope=row.scope,
        target=row.target,
        risk_level=row.risk_level,
        status=row.status,
        expires_at=row.expires_at,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        reason=row.reason,
        grant_mode=str(gm),
    )


class PermissionApproveBody(BaseModel):
    grant_mode: str = Field(
        default="once",
        description="once | session | always_workspace | always_repo_branch",
    )
    grant_session_hours: float | None = Field(default=8.0)
    session_id: str | None = Field(
        default=None,
        max_length=64,
        description="Web chat session id for host job correlation (defaults to stored value).",
    )


class PermissionApproveOut(BaseModel):
    reply: str
    permission: WebAccessPermissionOut
    related_jobs: list[AgentJobRead] = Field(default_factory=list)
    # Async path: client should poll GET /api/v1/web/jobs/{id} until terminal
    host_job_id: int | None = None
    job_status: str | None = None


@router.get("/requests/pending", response_model=list[WebAccessPermissionOut])
def list_pending_permission_requests(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    limit: int = 40,
) -> list[WebAccessPermissionOut]:
    st = (
        select(AccessPermission)
        .where(
            AccessPermission.owner_user_id == app_user_id[:64],
            AccessPermission.status == STATUS_PENDING,
        )
        .order_by(AccessPermission.id.desc())
        .limit(min(limit, 100))
    )
    rows = list(db.scalars(st).all())
    return [_perm_out(r) for r in rows]


def _grant_resume_permission_request(
    db: Session,
    app_user_id: str,
    permission_id: int,
    *,
    grant_mode: str,
    grant_session_hours: float | None,
    session_id: str | None,
) -> PermissionApproveOut:
    """Shared grant + host resume (POST approve + email link approve)."""
    granted = ap_grant_permission(
        db,
        app_user_id,
        permission_id,
        granted_by_user_id=app_user_id,
        grant_mode=grant_mode,
        grant_session_hours=grant_session_hours,
    )
    if not granted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not grant permission",
        )

    related: list[AgentJobRead] = []
    reply = "Permission granted. Running now."
    host_job_id: int | None = None
    job_status: str | None = None
    try:
        jid = resume_host_executor_after_grant(
            db,
            app_user_id,
            permission_id,
            web_session_id=session_id,
        )
        related = [job_service.get_job(db, app_user_id, jid)]
        host_job_id = int(jid)
        job_status = (related[0].status or None) if related else None
    except PermissionResumeError as e:
        logger.info("permission resume failed perm=%s err=%s", permission_id, e)
        reply = (
            f"Approved this permission, but Nexa could not queue the original action: {e}. "
            "Say **continue** or repeat your request in chat."
        )

    refreshed = db.get(AccessPermission, int(permission_id))
    perm = _perm_out(refreshed) if refreshed else _perm_out(granted)
    return PermissionApproveOut(
        reply=reply,
        permission=perm,
        related_jobs=related,
        host_job_id=host_job_id,
        job_status=job_status,
    )


@router.post("/requests/{permission_id}/approve", response_model=PermissionApproveOut)
def approve_permission_request(
    permission_id: int,
    body: PermissionApproveBody | None = None,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> PermissionApproveOut:
    bm = body or PermissionApproveBody()
    row = db.get(AccessPermission, int(permission_id))
    if not row or row.owner_user_id != app_user_id[:64]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    if row.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission request is not pending",
        )

    return _grant_resume_permission_request(
        db,
        app_user_id,
        permission_id,
        grant_mode=bm.grant_mode,
        grant_session_hours=bm.grant_session_hours,
        session_id=bm.session_id,
    )


def _email_perm_secret() -> str:
    return (get_settings().email_webhook_secret or "").strip()


@router.get("/requests/{permission_id}/email-approve", response_class=HTMLResponse)
def email_approve_permission_link(
    permission_id: int,
    token: str,
    mode: str = "once",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Browser-friendly approval for email channel (HMAC token; same grant semantics as POST approve).
    """
    secret = _email_perm_secret()
    if not secret:
        return HTMLResponse(
            "<html><body><p>Email permission links are not configured (EMAIL_WEBHOOK_SECRET).</p></body></html>",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    row = db.get(AccessPermission, int(permission_id))
    if not row or row.status != STATUS_PENDING:
        return HTMLResponse(
            "<html><body><p>Permission not found or no longer pending.</p></body></html>",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    owner = row.owner_user_id
    if not verify_email_permission_token(secret, int(permission_id), owner, token):
        return HTMLResponse(
            "<html><body><p>Invalid or expired approval link.</p></body></html>",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    m = (mode or "once").strip().lower()
    grant_mode = "session" if m == "session" else "once"
    try:
        out = _grant_resume_permission_request(
            db,
            owner,
            permission_id,
            grant_mode=grant_mode,
            grant_session_hours=8.0,
            session_id=None,
        )
    except HTTPException as e:
        det = e.detail
        if not isinstance(det, str):
            det = str(det)
        return HTMLResponse(
            f"<html><body><p>{html.escape(det)}</p></body></html>",
            status_code=int(e.status_code),
        )
    msg = html.escape(out.reply)
    return HTMLResponse(
        f"<html><body><h2>Permission updated</h2><p>{msg}</p></body></html>",
        status_code=status.HTTP_200_OK,
    )


@router.get("/requests/{permission_id}/email-deny", response_class=HTMLResponse)
def email_deny_permission_link(
    permission_id: int,
    token: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    secret = _email_perm_secret()
    if not secret:
        return HTMLResponse(
            "<html><body><p>Email permission links are not configured (EMAIL_WEBHOOK_SECRET).</p></body></html>",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    row = db.get(AccessPermission, int(permission_id))
    if not row or row.status != STATUS_PENDING:
        return HTMLResponse(
            "<html><body><p>Permission not found or no longer pending.</p></body></html>",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    owner = row.owner_user_id
    if not verify_email_permission_token(secret, int(permission_id), owner, token):
        return HTMLResponse(
            "<html><body><p>Invalid or expired link.</p></body></html>",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    denied = ap_deny_permission(db, owner, permission_id)
    if not denied:
        return HTMLResponse(
            "<html><body><p>Could not deny this permission.</p></body></html>",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return HTMLResponse(
        "<html><body><h2>Permission denied</h2><p>The request was denied.</p></body></html>",
        status_code=status.HTTP_200_OK,
    )


@router.post("/requests/{permission_id}/deny", response_model=WebAccessPermissionOut)
def deny_permission_request(
    permission_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebAccessPermissionOut:
    row = ap_deny_permission(db, app_user_id, permission_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found or not pending",
        )
    return _perm_out(row)
