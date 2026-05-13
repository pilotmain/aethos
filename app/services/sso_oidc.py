# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lazy OAuth client registry for OIDC SSO (authlib + Starlette)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from authlib.integrations.starlette_client import OAuth

_oauth: Any | None = None


def get_oidc_oauth() -> "OAuth":
    global _oauth
    if _oauth is not None:
        return _oauth
    from authlib.integrations.starlette_client import OAuth

    from app.core.config import get_settings

    s = get_settings()
    iss = (s.sso_oidc_issuer or "").strip().rstrip("/")
    if not iss:
        raise RuntimeError("SSO_OIDC_ISSUER is not configured")

    oauth = OAuth()
    oauth.register(
        name="oidc",
        client_id=(s.sso_client_id or "").strip(),
        client_secret=(s.sso_client_secret or "").strip(),
        server_metadata_url=f"{iss}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    _oauth = oauth
    return oauth


def reset_oidc_oauth_for_tests() -> None:
    global _oauth
    _oauth = None


__all__ = ["get_oidc_oauth", "reset_oidc_oauth_for_tests"]
