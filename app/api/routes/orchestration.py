# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 16a — REST delegation (Mission Control auth: ``X-User-Id`` + optional ``NEXA_WEB_API_TOKEN``)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.orchestration.delegate import run_delegation

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


class DelegateBody(BaseModel):
    agents: list[str] = Field(..., min_length=2)
    goal: str = Field(..., min_length=1, max_length=12_000)
    parallel: bool = False


@router.post("/delegate")
def post_delegate(
    body: DelegateBody,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_valid_web_user_id),
):
    """Create agent_team assignments for multiple handles and dispatch (or queue for approval)."""
    return run_delegation(
        db,
        user_id,
        body.agents,
        (body.goal or "").strip(),
        parallel=bool(body.parallel),
        channel="api",
    )
