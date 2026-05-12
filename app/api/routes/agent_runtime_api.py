# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""HTTP API for sessions_spawn and background_heartbeat (governed tool calls)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.agent_runtime.heartbeat import background_heartbeat
from app.services.agent_runtime.sessions import sessions_spawn

router = APIRouter(prefix="/agent-runtime", tags=["agent-runtime"])


@router.post("/sessions-spawn")
def post_sessions_spawn(
    body: dict[str, Any],
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    p = dict(body or {})
    p["requested_by"] = app_user_id
    try:
        return sessions_spawn(db, user_id=app_user_id, payload=p)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or "invalid spawn payload",
        ) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e) or "agent runtime disabled",
        ) from e


@router.post("/heartbeat")
def post_heartbeat(
    body: dict[str, Any],
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    try:
        return background_heartbeat(db, user_id=app_user_id, payload=dict(body or {}))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or "invalid heartbeat",
        ) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e) or "agent runtime disabled",
        ) from e
