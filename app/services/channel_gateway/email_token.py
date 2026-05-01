"""HMAC tokens for email permission links (no cookies / X-User-Id in mail clients)."""

from __future__ import annotations

import hashlib
import hmac


def email_permission_token(secret: str, permission_id: int, owner_user_id: str) -> str:
    """Deterministic token tying ``permission_id`` to ``owner_user_id`` (secret-key HMAC)."""
    msg = f"{permission_id}:{owner_user_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_email_permission_token(
    secret: str,
    permission_id: int,
    owner_user_id: str,
    token: str,
) -> bool:
    if not secret or not token:
        return False
    expected = email_permission_token(secret, permission_id, owner_user_id)
    return hmac.compare_digest(expected, token.strip())
