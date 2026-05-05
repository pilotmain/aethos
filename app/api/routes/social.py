"""Phase 22 — social media API (Bearer ``NEXA_CRON_API_TOKEN``)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.routes.cron_automation import verify_cron_token
from app.core.config import get_settings
from app.services.social.orchestrator import SocialOrchestrator, SocialPlatform

router = APIRouter(prefix="/social", tags=["social"])


def _require_social() -> None:
    if not get_settings().nexa_social_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"ok": False, "code": "SOCIAL_DISABLED", "error": "Set NEXA_SOCIAL_ENABLED=true"},
        )


class PostRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=32)
    content: str = Field(..., min_length=1, max_length=16_000)
    media_urls: list[str] | None = None
    reply_to: str | None = Field(default=None, max_length=64)


@router.post("/post")
async def api_post(
    request: PostRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_social()
    try:
        plat = SocialPlatform(request.platform.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown platform: {request.platform}",
        ) from exc
    orch = SocialOrchestrator()
    out = await orch.post(
        plat,
        request.content,
        media_urls=request.media_urls,
        reply_to=request.reply_to,
    )
    if not out.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=out,
        )
    return {"ok": True, **out}


@router.get("/posts/{platform}/{user_id}")
async def api_get_posts(
    platform: str,
    user_id: str,
    limit: int = 10,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_social()
    try:
        plat = SocialPlatform(platform.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown platform: {platform}",
        ) from exc
    orch = SocialOrchestrator()
    posts = await orch.get_posts(plat, user_id, limit)
    return {"ok": True, "platform": platform, "user_id": user_id, "posts": posts, "count": len(posts)}


@router.get("/search/{platform}")
async def api_search(
    platform: str,
    q: str,
    limit: int = 10,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    _require_social()
    try:
        plat = SocialPlatform(platform.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown platform: {platform}",
        ) from exc
    orch = SocialOrchestrator()
    results = await orch.search(plat, q, limit)
    return {"ok": True, "platform": platform, "query": q, "results": results, "count": len(results)}


__all__ = ["router"]
