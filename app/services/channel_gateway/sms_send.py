"""Twilio REST — outbound SMS."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.services.channel_gateway.rate_limit import acquire_outbound_slot
from app.services.channel_gateway.retry import outbound_with_retry

logger = logging.getLogger(__name__)

_MAX_SMS = 1600  # Twilio max for single-segment text; long messages are split by Twilio


def send_sms_text(
    *, to_e164: str, body: str, rate_limit_user_id: str | None = None
) -> dict[str, Any]:
    acquire_outbound_slot(channel="sms", user_id=rate_limit_user_id)

    def _send() -> dict[str, Any]:
        s = get_settings()
        sid = (s.twilio_account_sid or "").strip()
        token = (s.twilio_auth_token or "").strip()
        from_num = (s.twilio_from_number or "").strip()
        if not sid or not token or not from_num:
            raise RuntimeError("SMS not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER)")
        to_clean = normalize_to_address(to_e164)
        text = (body or "")[:_MAX_SMS]
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        payload = urlencode({"From": from_num, "To": to_clean, "Body": text})
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
                logger.warning("twilio send failed status=%s body=%s", r.status_code, r.text[:500])
                raise RuntimeError(f"Twilio API error: {e}") from e
            data = r.json()
        logger.info("sms sent to=%s sid=%s", to_clean[:16], data.get("sid"))
        return data

    return outbound_with_retry(channel="sms", operation="twilio_send", func=_send)


def normalize_to_address(raw: str) -> str:
    """Normalize phone for Twilio ``To`` (E.164 with leading +)."""
    d = "".join(c for c in (raw or "") if c.isdigit())
    if not d:
        raise ValueError("invalid SMS recipient")
    return f"+{d}"
