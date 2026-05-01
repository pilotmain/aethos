"""WhatsApp Cloud API — outbound text messages (Graph)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.channel_gateway.rate_limit import acquire_outbound_slot
from app.services.channel_gateway.retry import outbound_with_retry

logger = logging.getLogger(__name__)

GRAPH_VERSION = "v21.0"
# WhatsApp text body limit (conservative)
_MAX_BODY = 4096


def send_whatsapp_text(
    *, to_wa_id: str, body: str, rate_limit_user_id: str | None = None
) -> dict[str, Any]:
    """
    Send a text message to a WhatsApp user (``to`` = E.164 without +, as returned by webhooks).
    """
    acquire_outbound_slot(channel="whatsapp", user_id=rate_limit_user_id)

    def _send() -> dict[str, Any]:
        s = get_settings()
        token = (s.whatsapp_access_token or "").strip()
        phone_id = (s.whatsapp_phone_number_id or "").strip()
        if not token or not phone_id:
            raise RuntimeError("WhatsApp is not configured (WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID)")
        to_clean = "".join(c for c in (to_wa_id or "") if c.isdigit())
        if not to_clean:
            raise ValueError("invalid WhatsApp recipient")
        text = (body or "")[:_MAX_BODY]
        url = f"https://graph.facebook.com/{GRAPH_VERSION}/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        with httpx.Client(timeout=45.0) as client:
            r = client.post(url, headers=headers, json=payload)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "whatsapp send failed status=%s body=%s",
                    r.status_code,
                    r.text[:500],
                )
                raise RuntimeError(f"WhatsApp API error: {e}") from e
            data = r.json()
        logger.info("whatsapp sent to=%s msg_id=%s", to_clean[:12], (data.get("messages") or [{}])[0].get("id"))
        return data

    return outbound_with_retry(channel="whatsapp", operation="graph_send", func=_send)
