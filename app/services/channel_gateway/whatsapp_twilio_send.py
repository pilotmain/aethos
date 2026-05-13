# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Twilio REST — outbound WhatsApp (whatsapp:+E164 addresses)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.services.channel_gateway.rate_limit import acquire_outbound_slot
from app.services.channel_gateway.retry import outbound_with_retry
from app.services.channel_gateway.sms_send import normalize_to_address

logger = logging.getLogger(__name__)

_MAX_BODY = 1600


def _twilio_whatsapp_from_address() -> str:
    s = get_settings()
    explicit = (getattr(s, "twilio_whatsapp_from_number", None) or "").strip()
    if explicit:
        e = explicit if explicit.lower().startswith("whatsapp:") else f"whatsapp:{explicit}"
        return e
    base = (s.twilio_from_number or "").strip()
    if not base:
        raise RuntimeError("Twilio WhatsApp From not configured (TWILIO_WHATSAPP_FROM_NUMBER or TWILIO_FROM_NUMBER)")
    if base.lower().startswith("whatsapp:"):
        return base
    return f"whatsapp:{normalize_to_address(base)}"


def send_whatsapp_twilio_text(
    *, to_wa_digits: str, body: str, rate_limit_user_id: str | None = None
) -> dict[str, Any]:
    """Send a WhatsApp user message via Twilio (``To=whatsapp:+…``)."""
    acquire_outbound_slot(channel="whatsapp", user_id=rate_limit_user_id)

    def _send() -> dict[str, Any]:
        s = get_settings()
        sid = (s.twilio_account_sid or "").strip()
        token = (s.twilio_auth_token or "").strip()
        if not sid or not token:
            raise RuntimeError("Twilio not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)")
        to_addr = f"whatsapp:{normalize_to_address(to_wa_digits)}"
        from_addr = _twilio_whatsapp_from_address()
        text = (body or "")[:_MAX_BODY]
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = urlencode({"From": from_addr, "To": to_addr, "Body": text})
        with httpx.Client(timeout=45.0) as client:
            r = client.post(
                url,
                content=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(sid, token),
            )
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.warning("twilio whatsapp send failed status=%s body=%s", r.status_code, r.text[:500])
                raise RuntimeError(f"Twilio API error: {e}") from e
            data = r.json()
        logger.info("twilio whatsapp sent to=%s sid=%s", to_addr[:24], data.get("sid"))
        return data

    return outbound_with_retry(channel="whatsapp", operation="twilio_whatsapp_send", func=_send)


__all__ = ["send_whatsapp_twilio_text"]
