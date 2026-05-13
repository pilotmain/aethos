# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise OIDC SSO (optional) — login + callback on the API origin."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.services.jsonl_audit_log import log_jsonl_audit_event

router = APIRouter(prefix="/sso", tags=["sso"])


@router.get("/status")
def sso_status() -> dict[str, Any]:
    s = get_settings()
    ready = bool(
        getattr(s, "sso_enabled", False)
        and (s.sso_client_id or "").strip()
        and (s.sso_oidc_issuer or "").strip()
    )
    return {"sso_enabled": ready, "issuer_configured": bool((s.sso_oidc_issuer or "").strip())}


@router.get("/login")
async def sso_login(request: Request) -> RedirectResponse:
    s = get_settings()
    if not getattr(s, "sso_enabled", False):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="sso_disabled")
    if not (s.sso_client_id or "").strip() or not (s.sso_oidc_issuer or "").strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="sso_not_configured")
    try:
        from app.services.sso import get_oidc_oauth

        oauth = get_oidc_oauth()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"sso_init_failed: {exc}",
        ) from exc

    redirect_uri = (s.sso_redirect_uri or "").strip() or str(request.url_for("sso_oidc_callback"))
    try:
        return await oauth.oidc.authorize_redirect(request, redirect_uri)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"authorize_redirect_failed: {exc}",
        ) from exc


@router.get("/callback", name="sso_oidc_callback")
async def sso_callback(request: Request) -> RedirectResponse:
    s = get_settings()
    if not getattr(s, "sso_enabled", False):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="sso_disabled")
    try:
        from app.services.sso import get_oidc_oauth

        oauth = get_oidc_oauth()
        token = await oauth.oidc.authorize_access_token(request)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        log_jsonl_audit_event(user_id="unknown", action="sso.callback", outcome="error", details={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"sso_callback_failed: {exc}",
        ) from exc

    userinfo = token.get("userinfo") if isinstance(token, dict) else None
    if not isinstance(userinfo, dict):
        userinfo = {}
    sub = str(userinfo.get("sub") or token.get("sub") or "").strip()
    if not sub:
        raise HTTPException(status_code=400, detail="missing_oidc_subject")

    app_uid = f"oidc:{sub}"[:128]
    email = str(userinfo.get("email") or "").strip()
    log_jsonl_audit_event(
        user_id=app_uid,
        action="sso.login",
        outcome="success",
        details={"email": email} if email else {},
    )

    post = (s.sso_post_login_redirect or "http://localhost:3000/login").strip()
    from urllib.parse import urlencode

    q = urlencode({"x_user_id": app_uid})
    sep = "&" if "?" in post else "?"
    return RedirectResponse(f"{post}{sep}{q}", status_code=302)


__all__ = ["router"]
