"""
Phase 71 — Mission Control "Marketplace" web panel API.

The browser cannot use the cron-token-gated ``/clawhub`` endpoints (those require
``Authorization: Bearer <NEXA_CRON_API_TOKEN>``), so this router proxies the same
:class:`~app.services.skills.clawhub_client.ClawHubClient` and
:class:`~app.services.skills.installer.SkillInstaller` over the standard web auth
flow (``X-User-Id`` plus optional ``Authorization: Bearer <NEXA_WEB_API_TOKEN>``).

Read-only discovery (search / popular / metadata / installed list) is allowed for
any authenticated web user. Mutating operations (install / uninstall / update)
additionally require the caller to be the **Telegram-linked owner**, the same
trust gate the rest of the web surface uses for destructive actions.

The whole surface is gated by ``NEXA_MARKETPLACE_PANEL_ENABLED`` (default ``true``)
so operators can disable the marketplace panel without disabling the cron-side
``/clawhub`` automation endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.skills.clawhub_client import ClawHubClient
from app.services.skills.installer import SkillInstaller
from app.services.user_capabilities import (
    get_telegram_role_for_app_user,
    is_owner_role,
)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


def _ensure_enabled() -> None:
    settings = get_settings()
    if not bool(getattr(settings, "nexa_marketplace_panel_enabled", True)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Marketplace panel disabled (set NEXA_MARKETPLACE_PANEL_ENABLED=1 to enable).",
        )


def _require_owner(db: Session, app_user_id: str) -> None:
    role = get_telegram_role_for_app_user(db, app_user_id)
    if not is_owner_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Marketplace install / uninstall / update require the Telegram-linked owner.",
        )


class MarketplaceInstallBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    version: str = Field(default="latest", max_length=64)
    force: bool = Field(default=False, description="Bypass NEXA_CLAWHUB_REQUIRE_INSTALL_APPROVAL when set")


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
    if msg == "remote_metadata_unavailable":
        return HTTPException(status_code=502, detail=msg)
    if msg == "download_failed":
        return HTTPException(status_code=502, detail=msg)
    return HTTPException(status_code=500, detail=msg)


@router.get("/search")
async def marketplace_search(
    q: str,
    limit: int = 20,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    safe_limit = max(1, min(int(limit or 0) or 20, 100))
    results = await ClawHubClient().search_skills(q, safe_limit)
    return {"ok": True, "skills": [r.to_dict() for r in results]}


@router.get("/popular")
async def marketplace_popular(
    limit: int = 20,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    safe_limit = max(1, min(int(limit or 0) or 20, 100))
    results = await ClawHubClient().list_popular(safe_limit)
    return {"ok": True, "skills": [r.to_dict() for r in results]}


@router.get("/skill/{name}")
async def marketplace_skill_info(
    name: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    skill = await ClawHubClient().get_skill_info(name)
    if not skill:
        raise HTTPException(status_code=404, detail="skill_not_found")
    return {"ok": True, "skill": skill.to_dict()}


@router.get("/installed")
def marketplace_list_installed(
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    skills = SkillInstaller().list_installed()
    return {"ok": True, "skills": [s.to_dict() for s in skills]}


@router.post("/install")
async def marketplace_install(
    body: MarketplaceInstallBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    _require_owner(db, app_user_id)
    inst = SkillInstaller()
    ok, msg, skill_key = await inst.install(body.name, body.version, force=body.force)
    if not ok:
        raise _install_http_error(msg)
    return {"ok": True, "skill_name": skill_key, "message": msg}


@router.post("/uninstall/{name}")
async def marketplace_uninstall(
    name: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    _require_owner(db, app_user_id)
    inst = SkillInstaller()
    ok, msg = await inst.uninstall(name)
    if not ok:
        if msg == "not_found":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": "uninstalled"}


@router.post("/update/{name}")
async def marketplace_update(
    name: str,
    force: bool = False,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    _require_owner(db, app_user_id)
    inst = SkillInstaller()
    ok, msg = await inst.update(name, force=force)
    if not ok:
        if msg == "not_found":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": msg}
