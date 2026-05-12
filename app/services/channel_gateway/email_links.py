# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Build email permission approval URLs and human-readable link blocks."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.channel_gateway.email_token import email_permission_token


def _api_base() -> str:
    s = get_settings()
    return s.api_base_url.rstrip("/") + s.api_v1_prefix


def build_email_permission_links(permission_id: int, owner_user_id: str) -> dict[str, str]:
    """
    Returns ``once``, ``session``, ``deny`` URL strings, or empty dict if ``EMAIL_WEBHOOK_SECRET`` unset.
    """
    s = get_settings()
    secret = (s.email_webhook_secret or "").strip()
    if not secret:
        return {}
    token = email_permission_token(secret, int(permission_id), owner_user_id)
    base = _api_base()
    q = f"token={token}"
    return {
        "once": f"{base}/permissions/requests/{int(permission_id)}/email-approve?{q}&mode=once",
        "session": f"{base}/permissions/requests/{int(permission_id)}/email-approve?{q}&mode=session",
        "deny": f"{base}/permissions/requests/{int(permission_id)}/email-deny?{q}",
    }


def format_email_permission_text(permission_id: int, owner_user_id: str) -> str:
    """Plain-text block with approval links (for email body)."""
    links = build_email_permission_links(permission_id, owner_user_id)
    if not links:
        return (
            "Permission is required, but approval links are not available "
            "(set EMAIL_WEBHOOK_SECRET in the server environment).\n"
            "Approve or deny from the Web or Telegram session if available."
        )
    return (
        "Nexa needs your approval. Open one of the following links in your browser:\n\n"
        f"• Allow once:\n{links['once']}\n\n"
        f"• Allow for this session:\n{links['session']}\n\n"
        f"• Deny:\n{links['deny']}\n"
    )
