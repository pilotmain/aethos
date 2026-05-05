"""Shared API auth dependencies (cron token, web user, etc.)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_cron_token(authorization: str | None = Header(None)) -> None:
    """
    Require ``Authorization: Bearer <NEXA_CRON_API_TOKEN>`` for automation / internal routes.
    """
    tok = (get_settings().nexa_cron_api_token or "").strip()
    if not tok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXA_CRON_API_TOKEN is not configured",
        )
    if (authorization or "").strip() != f"Bearer {tok}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid cron token")


__all__ = ["verify_cron_token"]
