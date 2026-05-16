# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 22 persistent memory documents — GET/POST `/api/v1/nexa-memory`."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_valid_web_user_id
from app.privacy.memory_privacy import prepare_memory_write
from app.services.memory.memory_store import MemoryStore

router = APIRouter(prefix="/nexa-memory", tags=["nexa-memory"])


class NexaMemoryAppend(BaseModel):
    kind: str = Field(default="note", max_length=64)
    title: str = Field(default="", max_length=500)
    body: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def get_nexa_memory(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    store = MemoryStore()
    return store.read_document(app_user_id)


@router.post("")
def post_nexa_memory(
    body: NexaMemoryAppend,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    store = MemoryStore()
    b, t, priv = prepare_memory_write(body.body or "", body.title or "")
    meta = dict(body.meta or {})
    meta["privacy"] = priv
    rec = store.append_entry(
        app_user_id,
        kind=body.kind or "note",
        title=t or "",
        body_md=b or "",
        meta=meta,
    )
    return {"ok": True, "entry": rec}


__all__ = ["router"]
