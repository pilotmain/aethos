"""Skills API — `/api/v1/skills` (Phase 22)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_valid_web_user_id
from app.services.skills.registry import list_skill_docs, save_skill_doc

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillDefinition(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    inputs: list[str] = Field(default_factory=list)
    provider: str = Field(default="api", max_length=64)
    pii_policy: Literal["redact", "block", "allow"] = "redact"
    description: str = ""


@router.get("")
def skills_list(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    return {"ok": True, "skills": list_skill_docs(app_user_id)}


@router.post("")
def skills_create(
    body: SkillDefinition,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    doc = body.model_dump()
    path = save_skill_doc(app_user_id, body.name, doc)
    return {"ok": True, "path": str(path), "skill": doc}


__all__ = ["router"]
