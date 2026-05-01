"""REST API for user custom agents (Phase 20) — list/create/patch/delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.user_agent import UserAgent
from app.schemas.custom_agents_api import (
    CustomAgentCreateIn,
    CustomAgentCreateOut,
    CustomAgentDetail,
    CustomAgentPatchIn,
    CustomAgentsListOut,
    CustomAgentSummary,
)
from app.services.channel_gateway.origin_context import get_channel_origin
from app.services.custom_agent_parser import parse_custom_agent_from_prompt
from app.services.custom_agents import (
    _audit_custom_agent_event,
    can_user_create_custom_agents,
    create_custom_agent_from_prompt,
    delete_custom_agent,
    get_custom_agent,
    list_custom_agents,
    normalize_agent_key,
)

router = APIRouter(prefix="/custom-agents", tags=["custom-agents"])

_PREVIEW_LEN = 2400


def _to_summary(row: UserAgent) -> CustomAgentSummary:
    return CustomAgentSummary(
        handle=str(row.agent_key),
        display_name=str(row.display_name or ""),
        description=str(row.description or "")[:5000],
        safety_level=str(row.safety_level or "standard")[:32],
        enabled=bool(row.is_active),
    )


def _to_detail(row: UserAgent) -> CustomAgentDetail:
    sp = str(row.system_prompt or "")
    prev = sp[:_PREVIEW_LEN] + ("…" if len(sp) > _PREVIEW_LEN else "")
    base = _to_summary(row)
    return CustomAgentDetail(
        **base.model_dump(),
        instructions_preview=prev,
    )


def _list_agents_out(db: Session, app_user_id: str) -> CustomAgentsListOut:
    rows = list_custom_agents(db, app_user_id)
    return CustomAgentsListOut(agents=[_to_summary(r) for r in rows])


@router.get("", response_model=CustomAgentsListOut)
def list_custom_agents_api(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> CustomAgentsListOut:
    return _list_agents_out(db, app_user_id)


@router.get("/{handle}", response_model=CustomAgentDetail)
def get_custom_agent_api(
    handle: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> CustomAgentDetail:
    k = normalize_agent_key(handle.strip().lstrip("@"))
    row = get_custom_agent(db, app_user_id, k)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown custom agent `@{k}`")
    return _to_detail(row)


@router.post("", response_model=CustomAgentCreateOut)
def create_custom_agent_api(
    payload: CustomAgentCreateIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> CustomAgentCreateOut:
    ok_p, err = can_user_create_custom_agents(db, app_user_id)
    if not ok_p:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(err or "Custom agents are not available for this account."),
        )
    co = get_channel_origin()
    msg = create_custom_agent_from_prompt(
        db, user_id=app_user_id, prompt=payload.prompt, channel_origin=co
    )
    spec = parse_custom_agent_from_prompt(payload.prompt)
    key = normalize_agent_key(spec.handle) if spec else None
    row = get_custom_agent(db, app_user_id, key) if key else None
    success = row is not None and msg.strip().startswith("Created custom agent")
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg[:4000])
    return CustomAgentCreateOut(ok=True, agent=_to_summary(row), message=msg)


@router.patch("/{handle}", response_model=CustomAgentSummary)
def patch_custom_agent_api(
    handle: str,
    payload: CustomAgentPatchIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> CustomAgentSummary:
    k = normalize_agent_key(handle.strip().lstrip("@"))
    row = get_custom_agent(db, app_user_id, k)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown custom agent `@{k}`")
    if payload.enabled is not None:
        row.is_active = bool(payload.enabled)
    if payload.description is not None:
        row.description = str(payload.description)[:20_000]
    if payload.instructions_append:
        add = f"\n\n[API update]: {str(payload.instructions_append).strip()[:8000]}"
        row.system_prompt = (row.system_prompt or "") + add
    db.add(row)
    db.commit()
    db.refresh(row)
    _audit_custom_agent_event(
        db,
        event_type="custom_agent.updated",
        actor="nexa",
        message=f"REST PATCH @{k}",
        user_id=app_user_id,
        metadata={"handle": k, "source": "api"},
    )
    return _to_summary(row)


@router.delete("/{handle}")
def delete_custom_agent_api(
    handle: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> Response:
    k = normalize_agent_key(handle.strip().lstrip("@"))
    if not get_custom_agent(db, app_user_id, k):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown custom agent `@{k}`")
    delete_custom_agent(db, app_user_id, k)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
