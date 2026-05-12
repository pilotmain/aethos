# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Outbound Apple Messages — POST to configured provider URL (Phase 11)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.channel_gateway.rate_limit import acquire_outbound_slot
from app.services.channel_gateway.retry import outbound_with_retry

logger = logging.getLogger(__name__)

_MAX_TEXT = 8000


def send_apple_message_text(
    *, to: str, body: str, rate_limit_user_id: str | None = None
) -> dict[str, Any]:
    """
    POST plain text reply to ``APPLE_MESSAGES_PROVIDER_URL``.

    Uses ``Authorization: Bearer`` with ``APPLE_MESSAGES_ACCESS_TOKEN`` and includes
    ``APPLE_MESSAGES_BUSINESS_ID`` in the JSON body for provider routing.
    """
    acquire_outbound_slot(channel="apple_messages", user_id=rate_limit_user_id)

    def _send() -> dict[str, Any]:
        s = get_settings()
        url = (s.apple_messages_provider_url or "").strip()
        token = (s.apple_messages_access_token or "").strip()
        biz = (s.apple_messages_business_id or "").strip()
        if not url or not token or not biz:
            raise RuntimeError(
                "Apple Messages not configured (APPLE_MESSAGES_PROVIDER_URL / "
                "APPLE_MESSAGES_ACCESS_TOKEN / APPLE_MESSAGES_BUSINESS_ID)"
            )
        cid = (to or "").strip()
        if not cid:
            raise ValueError("missing to (customer_id)")
        text = (body or "")[:_MAX_TEXT]
        payload = {
            "business_id": biz,
            "customer_id": cid,
            "text": text,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, content=json.dumps(payload), headers=headers)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "apple messages send failed status=%s body=%s", r.status_code, r.text[:500]
                )
                raise RuntimeError(f"Apple Messages provider error: {e}") from e
            data: dict[str, Any] = {}
            if r.text:
                try:
                    data = r.json()
                except json.JSONDecodeError:
                    data = {"raw": r.text[:500]}
        logger.info("apple messages sent customer=%s", cid[:24])
        return data

    return outbound_with_retry(channel="apple_messages", operation="provider_send", func=_send)
