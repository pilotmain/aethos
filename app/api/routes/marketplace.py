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

Compatibility aliases (same auth + behavior): ``GET /marketplace/skills/search`` →
``GET /marketplace/search``; ``POST /marketplace/check-updates`` →
``POST /marketplace/-/check-updates-now``.

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


async def _marketplace_search_impl(
    q: str,
    limit: int = 20,
    category: str | None = None,
) -> dict[str, Any]:
    _ensure_enabled()
    safe_limit = max(1, min(int(limit or 0) or 20, 100))
    cat = (category or "").strip().lower() or None
    results = await ClawHubClient().search_skills(q, safe_limit, category=cat)
    return {"ok": True, "skills": [r.to_dict() for r in results]}


@router.get("/search")
async def marketplace_search(
    q: str,
    limit: int = 20,
    category: str | None = None,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    return await _marketplace_search_impl(q, limit, category)


@router.get("/skills/search")
async def marketplace_skills_search_alias(
    q: str,
    limit: int = 20,
    category: str | None = None,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Alias for ``GET /marketplace/search`` (clients that namespace under ``/skills``)."""

    return await _marketplace_search_impl(q, limit, category)


@router.get("/popular")
async def marketplace_popular(
    limit: int = 20,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    safe_limit = max(1, min(int(limit or 0) or 20, 100))
    results = await ClawHubClient().list_popular(safe_limit)
    return {"ok": True, "skills": [r.to_dict() for r in results]}


@router.get("/featured")
async def marketplace_featured(
    limit: int = 12,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Phase 75 — curated "Featured" list. Defensive on 404 (returns []).

    Hidden from the UI when ``NEXA_MARKETPLACE_FEATURED_PANEL_ENABLED=false``
    (the endpoint still answers — the toggle is presentation-only — so
    existing automation can poll it without adding a new feature flag).
    """
    _ensure_enabled()
    safe_limit = max(1, min(int(limit or 0) or 12, 50))
    results = await ClawHubClient().list_featured(safe_limit)
    return {
        "ok": True,
        "panel_enabled": bool(
            getattr(get_settings(), "nexa_marketplace_featured_panel_enabled", True)
        ),
        "skills": [r.to_dict() for r in results],
    }


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


@router.get("/skill/{name}/details")
async def marketplace_skill_details(
    name: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Phase 75 — extended skill payload for the detail modal.

    Same upstream call as ``/skill/{name}``; the response is reshaped to
    surface the documentation (``readme_url``, ``changelog_url``), the
    cross-skill ``skill_dependencies`` graph, and the requested
    ``permissions``. The actual body of the README / changelog is NOT
    fetched server-side (the modal can render the URLs as links); this
    keeps the endpoint cheap and CSP-safe.
    """
    _ensure_enabled()
    skill = await ClawHubClient().get_skill_info(name)
    if not skill:
        raise HTTPException(status_code=404, detail="skill_not_found")
    payload = skill.to_dict()
    return {
        "ok": True,
        "skill": payload,
        "documentation": {
            "readme_url": payload.get("readme_url", ""),
            "changelog_url": payload.get("changelog_url", ""),
            "manifest_url": payload.get("manifest_url", ""),
        },
        "dependencies": payload.get("skill_dependencies", []),
        "permissions": payload.get("permissions", []),
    }


@router.get("/categories")
async def marketplace_categories(
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Phase 75 — derived list of categories (popular ∪ featured tags+category).

    Cheap helper for the UI filter chips. Operators don't need to maintain
    a hand-curated list — we surface whatever the registry already returns
    via popular / featured. Empty list when the registry is silent.
    """
    _ensure_enabled()
    client = ClawHubClient()
    popular = await client.list_popular(limit=50)
    featured = await client.list_featured(limit=20)
    bag: set[str] = set()
    for s in (*popular, *featured):
        if s.category:
            bag.add(s.category)
    return {"ok": True, "categories": sorted(bag)}


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


async def _marketplace_check_updates_now_impl(
    db: Session,
    app_user_id: str,
) -> dict[str, Any]:
    """Phase 75 — owner-triggered immediate update probe.

    Calls :meth:`SkillUpdateChecker.scan_once` directly so the operator
    doesn't have to wait for the periodic interval (default 1 day). This
    is **notify-only** — it stamps ``available_version`` on each installed
    row but never re-installs.
    """
    _ensure_enabled()
    _require_owner(db, app_user_id)
    from app.services.skills.update_checker import get_update_checker

    counters = await get_update_checker().scan_once()
    return {"ok": True, "counters": counters}


@router.post("/-/check-updates-now")
async def marketplace_check_updates_now(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    return await _marketplace_check_updates_now_impl(db, app_user_id)


@router.post("/check-updates")
async def marketplace_check_updates_alias(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Alias for ``POST /marketplace/-/check-updates-now``."""

    return await _marketplace_check_updates_now_impl(db, app_user_id)


@router.get("/-/capabilities")
def marketplace_capabilities(
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Phase 75 — single-shot snapshot the UI uses for banners/toggles.

    Surfaces the toggles operators care about: clawhub on/off, sandbox
    mode, the permission allowlist (so the UI can warn about skills that
    request beyond what's allowed), the auto-update notify-only flag,
    and the featured panel toggle.
    """
    _ensure_enabled()
    s = get_settings()
    allow_raw = (
        getattr(s, "nexa_marketplace_skill_permissions_allowlist", "") or ""
    )
    allow = [p.strip().lower() for p in str(allow_raw).split(",") if p.strip()]
    return {
        "ok": True,
        "clawhub_enabled": bool(getattr(s, "nexa_clawhub_enabled", True)),
        "panel_enabled": bool(getattr(s, "nexa_marketplace_panel_enabled", True)),
        "featured_panel_enabled": bool(
            getattr(s, "nexa_marketplace_featured_panel_enabled", True)
        ),
        "auto_update_skills": bool(
            getattr(s, "nexa_marketplace_auto_update_skills", False)
        ),
        "update_check_interval_seconds": int(
            getattr(s, "nexa_marketplace_update_check_interval_seconds", 86400) or 0
        ),
        "sandbox_mode": bool(getattr(s, "nexa_marketplace_sandbox_mode", True)),
        "skill_timeout_seconds": int(
            getattr(s, "nexa_marketplace_skill_timeout_seconds", 30) or 0
        ),
        "permissions_allowlist": allow,
        "trusted_publishers": [
            p.strip().lower()
            for p in str(getattr(s, "nexa_clawhub_trusted_publishers", "") or "").split(",")
            if p.strip()
        ],
    }
