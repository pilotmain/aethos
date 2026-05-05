"""ClawHub marketplace API — Bearer ``NEXA_CRON_API_TOKEN`` (same gate as cron automation)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import verify_cron_token
from app.services.skills.clawhub_client import ClawHubClient
from app.services.skills.installer import SkillInstaller

router = APIRouter(prefix="/clawhub", tags=["clawhub"])

_client = ClawHubClient()


class InstallBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    version: str = Field(default="latest", max_length=64)


def _install_http_error(msg: str) -> HTTPException:
    if msg == "install_requires_approval_force_false":
        return HTTPException(status_code=403, detail=msg)
    if msg == "publisher_not_trusted":
        return HTTPException(status_code=403, detail=msg)
    if msg == "signature_required_missing":
        return HTTPException(status_code=400, detail=msg)
    if msg == "already_installed":
        return HTTPException(status_code=409, detail=msg)
    if msg == "clawhub_disabled":
        return HTTPException(status_code=503, detail=msg)
    return HTTPException(status_code=500, detail=msg)


@router.get("/search")
async def search_skills(
    q: str,
    limit: int = 20,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    results = await _client.search_skills(q, limit)
    return {"ok": True, "skills": [r.to_dict() for r in results]}


@router.get("/popular")
async def popular_skills(limit: int = 20, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    results = await _client.list_popular(limit)
    return {"ok": True, "skills": [r.to_dict() for r in results]}


@router.get("/skill/{name}")
async def get_skill(name: str, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    skill = await _client.get_skill_info(name)
    if not skill:
        raise HTTPException(status_code=404, detail="skill_not_found")
    return {"ok": True, "skill": skill.to_dict()}


@router.post("/install")
async def install_skill(body: InstallBody, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    inst = SkillInstaller()
    ok, msg, skill_key = await inst.install(body.name, body.version, force=False)
    if not ok:
        raise _install_http_error(msg)
    return {"ok": True, "skill_name": skill_key, "message": msg}


@router.post("/uninstall/{name}")
async def uninstall_skill(name: str, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    inst = SkillInstaller()
    ok, msg = await inst.uninstall(name)
    if not ok:
        if msg == "not_found":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": "uninstalled"}


@router.post("/update/{name}")
async def update_skill(name: str, _: None = Depends(verify_cron_token)) -> dict[str, Any]:
    inst = SkillInstaller()
    ok, msg = await inst.update(name, force=False)
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": msg}


@router.get("/installed")
async def list_installed(_: None = Depends(verify_cron_token)) -> dict[str, Any]:
    inst = SkillInstaller()
    skills = inst.list_installed()
    return {"ok": True, "skills": [s.to_dict() for s in skills]}
