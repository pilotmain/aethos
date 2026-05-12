# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Browser automation API — Phase 14 (Bearer ``NEXA_CRON_API_TOKEN``, same as cron)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import verify_cron_token
from app.services.browser.controller import get_browser_controller

router = APIRouter(prefix="/browser", tags=["browser"])


class NavigateRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=8000)
    wait_until: str = Field(default="domcontentloaded", max_length=32)


@router.post("/navigate")
async def api_navigate(
    body: NavigateRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().navigate(body.url.strip(), wait_until=body.wait_until.strip())
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "navigate failed")
    return {"ok": True, "output": r.output}


class ClickRequest(BaseModel):
    selector: str = Field(..., min_length=1, max_length=2000)


@router.post("/click")
async def api_click(
    body: ClickRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().click(body.selector)
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "click failed")
    return {"ok": True, "output": r.output}


class FillRequest(BaseModel):
    selector: str = Field(..., min_length=1, max_length=2000)
    value: str = Field(..., max_length=50_000)


@router.post("/fill")
async def api_fill(
    body: FillRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().fill(body.selector, body.value)
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "fill failed")
    return {"ok": True, "output": r.output}


class EvaluateRequest(BaseModel):
    script: str = Field(..., min_length=1, max_length=50_000)


@router.post("/evaluate")
async def api_evaluate(
    body: EvaluateRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().evaluate(body.script)
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "evaluate failed")
    return {"ok": True, "output": r.output}


class TextRequest(BaseModel):
    selector: str = Field(..., min_length=1, max_length=2000)


@router.post("/text")
async def api_text(
    body: TextRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().get_text(body.selector)
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "get_text failed")
    return {"ok": True, "output": r.output}


class HtmlRequest(BaseModel):
    selector: str | None = Field(default=None, max_length=2000)


@router.post("/html")
async def api_html(
    body: HtmlRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().get_html(body.selector)
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "get_html failed")
    return {"ok": True, "output": r.output}


@router.get("/screenshot")
async def api_screenshot(
    name: str | None = Query(default=None, max_length=240),
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().screenshot(name)
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "screenshot failed")
    return {"ok": True, "screenshot_path": r.screenshot_path, "output": r.output}


@router.get("/screenshot/base64")
async def api_screenshot_base64(
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    r = await get_browser_controller().screenshot_base64()
    if not r.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=r.error or "screenshot failed")
    return {"ok": True, "image_base64": r.output}


class SkillRunRequest(BaseModel):
    skill_name: str = Field(..., min_length=3, max_length=128)
    input: dict[str, Any] = Field(default_factory=dict)


@router.post("/skill")
async def api_run_skill(
    body: SkillRunRequest,
    _: None = Depends(verify_cron_token),
) -> dict[str, Any]:
    from app.services.skills.plugin_registry import get_plugin_skill_registry

    reg = get_plugin_skill_registry()
    res = await reg.execute_skill(body.skill_name.strip(), dict(body.input or {}))
    if not res.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=res.error or "skill failed",
        )
    return {"ok": True, "output": res.output}


__all__ = ["router"]
