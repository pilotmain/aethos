"""REST API for agent organizations and assignments (orchestration layer)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.agent_team import AgentOrganization
from app.schemas.agent_organization import (
    AgentAssignmentCreate,
    AgentOrganizationCreate,
    AgentOrganizationOut,
    AgentRoleCreate,
)
from app.services.agent_team.service import (
    DuplicateAssignmentError,
    assign_agent_to_org,
    assignment_to_dict,
    cancel_assignment,
    create_agent_organization,
    create_assignment,
    dispatch_assignment,
    get_assignment_status,
    get_or_create_default_organization,
    list_assignments_for_user,
)

router = APIRouter(tags=["agent-organization"])


def _org_or_404(db: Session, org_id: int, user_id: str) -> AgentOrganization:
    row = db.get(AgentOrganization, org_id)
    if not row or row.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return row


@router.get("/agent-orgs")
def list_agent_orgs(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    uid = (app_user_id or "").strip()[:64]
    rows = list(
        db.scalars(
            select(AgentOrganization).where(AgentOrganization.user_id == uid).order_by(AgentOrganization.id.asc())
        ).all()
    )
    return {
        "organizations": [
            {"id": r.id, "name": r.name, "description": r.description, "enabled": r.enabled} for r in rows
        ]
    }


@router.post("/agent-orgs", response_model=AgentOrganizationOut)
def create_org_api(
    payload: AgentOrganizationCreate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> AgentOrganizationOut:
    org = create_agent_organization(
        db,
        user_id=app_user_id,
        name=payload.name,
        description=payload.description,
    )
    return AgentOrganizationOut(
        id=org.id,
        name=org.name,
        description=org.description,
        enabled=bool(org.enabled),
    )


@router.get("/agent-orgs/{org_id}")
def get_org_api(
    org_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    uid = (app_user_id or "").strip()[:64]
    org = _org_or_404(db, org_id, uid)
    return {"id": org.id, "name": org.name, "description": org.description, "enabled": org.enabled}


@router.post("/agent-orgs/{org_id}/agents")
def add_role_api(
    org_id: int,
    payload: AgentRoleCreate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    uid = (app_user_id or "").strip()[:64]
    _org_or_404(db, org_id, uid)
    row = assign_agent_to_org(
        db,
        organization_id=org_id,
        agent_handle=payload.agent_handle,
        role=payload.role,
        skills=payload.skills,
        reports_to_handle=payload.reports_to_handle,
        responsibilities=payload.responsibilities,
    )
    return {"id": row.id, "agent_handle": row.agent_handle, "role": row.role}


@router.get("/agent-assignments")
def list_assignments_api(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    return {"assignments": list_assignments_for_user(db, app_user_id, limit=80)}


@router.post("/agent-assignments")
def create_assignment_api(
    payload: AgentAssignmentCreate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    uid = (app_user_id or "").strip()[:64]
    oid = payload.organization_id
    if oid is None:
        oid = get_or_create_default_organization(db, uid).id
    else:
        _org_or_404(db, oid, uid)
    try:
        row = create_assignment(
            db,
            user_id=uid,
            assigned_to_handle=payload.assigned_to_handle,
            title=payload.title,
            description=payload.description,
            organization_id=oid,
            assigned_by_handle="user",
            priority=payload.priority,
            input_json=payload.input_json,
            channel="web",
        )
    except DuplicateAssignmentError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate_assignment",
                "existing_assignment_id": e.existing.id,
                "message": f"Open assignment #{e.existing.id} already matches this task (same agent and title).",
            },
        ) from e
    return assignment_to_dict(row)


@router.get("/agent-assignments/{assignment_id}")
def get_assignment_api(
    assignment_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    st = get_assignment_status(db, assignment_id=assignment_id, user_id=app_user_id)
    if not st:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    return st


@router.post("/agent-assignments/{assignment_id}/dispatch")
def dispatch_api(
    assignment_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    return dispatch_assignment(db, assignment_id=assignment_id, user_id=app_user_id)


@router.post("/agent-assignments/{assignment_id}/cancel")
def cancel_api(
    assignment_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    return cancel_assignment(db, assignment_id=assignment_id, user_id=app_user_id)
