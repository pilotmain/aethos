# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""JWT access tokens for cloud SaaS users (HS256, ``NEXA_SECRET_KEY``)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def create_cloud_access_token(*, user_id: str, email: str, organization_id: str) -> str:
    s = get_settings()
    secret = (s.nexa_secret_key or "").strip()
    if not secret:
        raise RuntimeError("NEXA_SECRET_KEY is required for cloud JWT issuance")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=max(1, int(s.access_token_expire_days or 30)))
    payload = {
        "sub": user_id,
        "email": email,
        "org_id": organization_id,
        "typ": "aethos_cloud",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_cloud_access_token_payload(token: str) -> dict[str, object]:
    s = get_settings()
    secret = (s.nexa_secret_key or "").strip()
    if not secret:
        raise RuntimeError("NEXA_SECRET_KEY is required for cloud JWT verification")
    return jwt.decode(token, secret, algorithms=["HS256"])


__all__ = ["create_cloud_access_token", "decode_cloud_access_token_payload"]
