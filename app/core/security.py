# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

import logging

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.services.web_user_id import WEB_USER_ID_INVALID, validate_web_user_id

logger = logging.getLogger(__name__)


async def get_current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    return x_user_id


async def get_web_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    """X-User-Id plus optional bearer when :envvar:`NEXA_WEB_API_TOKEN` is set."""
    token = (get_settings().nexa_web_api_token or "").strip()
    if token:
        if not authorization or not (authorization or "").lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization: Bearer",
            )
        got = (authorization[7:]).strip() if len(authorization) > 7 else ""
        if got != token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            )
    if not (x_user_id and x_user_id.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    return x_user_id.strip()


async def get_valid_web_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    """
    Like :func:`get_web_user_id`, but :func:`~app.services.web_user_id.validate_web_user_id` runs
    on the header. Invalid formats are HTTP 400 with a constant detail; nothing user-supplied
    is logged or returned.
    """
    token = (get_settings().nexa_web_api_token or "").strip()
    if token:
        if not authorization or not (authorization or "").lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization: Bearer",
            )
        got = (authorization[7:]).strip() if len(authorization) > 7 else ""
        if got != token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            )
    if not (x_user_id and x_user_id.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    try:
        return validate_web_user_id(x_user_id)
    except ValueError:
        logger.warning("Invalid X-User-Id format received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=WEB_USER_ID_INVALID,
        ) from None
