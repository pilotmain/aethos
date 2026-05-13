# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Map vendor webhook shapes to :class:`~app.channels.base.InboundMessage` (diagnostics / new adapters)."""

from __future__ import annotations

from typing import Any

from app.channels.base import InboundMessage
from app.services.channel_gateway.sms_adapter import twilio_form_to_raw_event
from app.services.channel_gateway.whatsapp_twilio import twilio_form_to_whatsapp_raw_event


def slack_message_event_to_inbound(body: dict[str, Any]) -> InboundMessage | None:
    """
    Slack Events API envelope: ``{"event": {"user", "channel", "text", …}, "team_id": …}``.
    Returns None when ``event`` is missing or not a user message.
    """
    if not isinstance(body, dict):
        return None
    ev = body.get("event")
    if not isinstance(ev, dict):
        return None
    uid = str(ev.get("user") or "").strip()
    ch = str(ev.get("channel") or "").strip()
    if not uid:
        return None
    text = str(ev.get("text") or "").strip()
    raw = {"body": body, "event": ev}
    return InboundMessage(channel="slack", user_id=uid, chat_id=ch or uid, text=text, raw_payload=raw)


def twilio_sms_form_to_inbound(form: dict[str, str]) -> InboundMessage:
    """Twilio SMS form (``From`` E.164, ``Body``)."""
    raw = twilio_form_to_raw_event(form)
    frm = str(raw.get("From") or "").strip()
    to = str(raw.get("To") or "").strip()
    return InboundMessage(
        channel="sms",
        user_id=frm,
        chat_id=to or frm,
        text=str(raw.get("Body") or "").strip(),
        raw_payload=dict(raw),
    )


def twilio_whatsapp_form_to_inbound(form: dict[str, str]) -> InboundMessage:
    """Twilio WhatsApp form (``From`` starts with ``whatsapp:``)."""
    raw = twilio_form_to_whatsapp_raw_event(form)
    digits = str(raw.get("from") or "").strip()
    return InboundMessage(
        channel="whatsapp",
        user_id=digits,
        chat_id=digits,
        text=str(raw.get("text") or "").strip(),
        raw_payload=dict(raw),
    )


def discord_py_message_to_inbound(message: Any) -> InboundMessage:
    """``discord.py`` :class:`discord.Message` → :class:`InboundMessage` (optional dependency)."""
    author = getattr(message, "author", None)
    user_id = str(getattr(author, "id", "") or "").strip() or "unknown"
    channel = getattr(message, "channel", None)
    chat_id = str(getattr(channel, "id", "") or "").strip() or user_id
    text = str(getattr(message, "content", "") or "").strip()
    return InboundMessage(
        channel="discord",
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        raw_payload={"message_id": str(getattr(message, "id", "") or "")},
    )


__all__ = [
    "discord_py_message_to_inbound",
    "slack_message_event_to_inbound",
    "twilio_sms_form_to_inbound",
    "twilio_whatsapp_form_to_inbound",
]
