# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
JWT access tokens for the Phase 30 mobile app (HS256, ``NEXA_SECRET_KEY``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings


class MobileTokenError(Exception):
    """Invalid or expired mobile JWT."""


def create_mobile_access_token(user_id: str, display_name: str | None = None) -> str:
    s = get_settings()
    secret = (s.nexa_secret_key or "").strip()
    if not secret:
        raise RuntimeError("NEXA_SECRET_KEY is required for mobile JWT auth")
    hours = max(1, int(getattr(s, "nexa_mobile_token_ttl_hours", 168) or 168))
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "name": display_name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=hours)).timestamp()),
        "typ": "aethos_mobile",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_mobile_access_token(token: str) -> dict[str, Any]:
    s = get_settings()
    secret = (s.nexa_secret_key or "").strip()
    if not secret:
        raise MobileTokenError("server missing signing key")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise MobileTokenError(str(exc)) from exc
    if payload.get("typ") not in ("aethos_mobile", "nexa_mobile"):
        raise MobileTokenError("wrong token type")
    return payload


__all__ = [
    "MobileTokenError",
    "create_mobile_access_token",
    "decode_mobile_access_token",
]
