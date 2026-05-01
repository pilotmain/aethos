"""Shared-secret verification for Apple Messages provider webhooks (Phase 11)."""

from __future__ import annotations

import hmac
import logging

logger = logging.getLogger(__name__)


def verify_apple_messages_webhook_secret(
    *,
    configured_secret: str | None,
    header_value: str | None,
) -> bool:
    """
    Compare ``X-Apple-Messages-Webhook-Secret`` to :envvar:`APPLE_MESSAGES_WEBHOOK_SECRET`.

    When ``configured_secret`` is empty, callers should skip enforcement (dev/local).
    """
    cfg = (configured_secret or "").strip()
    if not cfg:
        return True
    got = (header_value or "").strip()
    if not got:
        return False
    return hmac.compare_digest(cfg, got)
