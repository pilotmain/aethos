# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Twilio → WhatsApp (user) inbound: map webhook form to the same shape as Meta Cloud extracts."""

from __future__ import annotations

import re
from typing import Any

_WA_FROM = re.compile(r"^whatsapp:", re.I)


def is_twilio_whatsapp_from(address: str) -> bool:
    return bool(_WA_FROM.match((address or "").strip()))


def twilio_form_to_whatsapp_raw_event(form: dict[str, str]) -> dict[str, Any]:
    """
    Twilio inbound ``From`` for WhatsApp is ``whatsapp:+E164``.

    Output matches :class:`~app.services.channel_gateway.whatsapp_adapter.WhatsAppAdapter`
    expectations: ``from`` (digits only), ``text``, ``message_id``.
    """
    from_raw = str(form.get("From") or "").strip()
    if not from_raw:
        raise ValueError("missing From")
    if not is_twilio_whatsapp_from(from_raw):
        raise ValueError("From is not a Twilio WhatsApp address")
    digits = re.sub(r"\D", "", from_raw)
    if len(digits) < 4:
        raise ValueError("invalid WhatsApp From")
    return {
        "from": digits,
        "text": str(form.get("Body") or "").strip(),
        "message_id": str(form.get("SmsSid") or form.get("MessageSid") or "").strip() or None,
        "display_name": None,
        "provider": "twilio_whatsapp",
    }
