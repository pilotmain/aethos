# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Legacy REST prefix ``/api/v1/memory`` — removed (HTTP 410).

Agent memory (preferences, soul, notes) lives under ``/api/v1/web/memory/…``.
Persistent Nexa memory documents: ``/api/v1/nexa-memory``.

Phase 15 — POST ``/memory/recall`` (Bearer ``NEXA_CRON_API_TOKEN``) for chunked active recall.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import verify_cron_token

router = APIRouter(prefix="/memory", tags=["memory"])

_DETAIL = (
    "Legacy endpoint removed. Use GET/POST /api/v1/nexa-memory for persistent memory documents; "
    "use /api/v1/web/memory/… for agent preferences, state, notes, soul, forget (authenticated web paths)."
)


def _gone() -> None:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=_DETAIL)


@router.get("")
def memory_root_gone() -> None:
    _gone()


@router.put("/preferences")
def memory_preferences_gone() -> None:
    _gone()


@router.get("/state")
def memory_state_gone() -> None:
    _gone()


@router.post("/remember")
def memory_remember_gone() -> None:
    _gone()


@router.patch("/notes")
def memory_notes_patch_gone() -> None:
    _gone()


@router.post("/notes/delete")
def memory_notes_delete_gone() -> None:
    _gone()


@router.post("/forget")
def memory_forget_gone() -> None:
    _gone()


@router.put("/soul")
def memory_soul_gone() -> None:
    _gone()


class ActiveRecallRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    user_id: str = Field(..., min_length=1, max_length=128)
    k: int | None = Field(default=None, ge=1, le=48)


@router.post("/recall")
def memory_active_recall(
    body: ActiveRecallRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    """Chunked vector recall over filesystem memory (same Bearer as cron / browser automation)."""
    from app.services.memory.active_memory import ActiveMemoryService

    hits = ActiveMemoryService().recall(
        body.user_id.strip(),
        body.query.strip(),
        limit=body.k,
    )
    return {"ok": True, "hits": hits, "count": len(hits)}
