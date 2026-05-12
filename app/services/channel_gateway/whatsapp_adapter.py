# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""WhatsApp Cloud API adapter — identity + normalization for Channel Gateway (Phase 9)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel_user import ChannelUser
from app.services.channel_gateway.base import ChannelAdapter
from app.services.channel_gateway.identity import resolve_channel_user
from app.services.channel_gateway.whatsapp_send import send_whatsapp_text

_WA_DIGITS = re.compile(r"^\d{4,20}$")


def whatsapp_default_user_id(provider_user_id: str) -> str:
    """Stable Nexa id: ``wa_<digits>`` (distinct from ``tg_*``, ``em_*``, …)."""
    d = re.sub(r"\D", "", (provider_user_id or "").strip())
    if not _WA_DIGITS.match(d):
        raise ValueError("invalid WhatsApp user id")
    return f"wa_{d}"


def extract_whatsapp_inbound_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Parse Meta ``whatsapp_business_account`` webhook JSON into simple inbound dicts.

    Each item: ``from``, ``message_id``, ``text``, optional ``display_name``.
    Only ``type == text`` messages are returned (Phase 9 scope).
    """
    out: list[dict[str, Any]] = []
    if (payload or {}).get("object") != "whatsapp_business_account":
        return out
    for ent in payload.get("entry") or []:
        for ch in ent.get("changes") or []:
            val = ch.get("value") or {}
            contact_map: dict[str, str] = {}
            for c in val.get("contacts") or []:
                wa_id = (c.get("wa_id") or "").strip()
                prof = (c.get("profile") or {}) if isinstance(c.get("profile"), dict) else {}
                name = (prof.get("name") or "").strip()
                if wa_id:
                    contact_map[wa_id] = name
            for msg in val.get("messages") or []:
                if (msg.get("type") or "").lower() != "text":
                    continue
                from_id = (msg.get("from") or "").strip()
                if not from_id:
                    continue
                mid = (msg.get("id") or "").strip()
                text_body = ((msg.get("text") or {}).get("body") or "").strip()
                out.append(
                    {
                        "from": from_id,
                        "message_id": mid or None,
                        "text": text_body,
                        "display_name": contact_map.get(from_id),
                    }
                )
    return out


class WhatsAppAdapter(ChannelAdapter):
    channel = "whatsapp"

    def resolve_app_user_id(self, db: Session, raw_event: Any) -> str:
        if not isinstance(raw_event, dict):
            raise ValueError("whatsapp raw_event must be a dict")
        uid = (raw_event.get("from") or "").strip()
        if not uid:
            raise ValueError("missing WhatsApp sender id")
        default = whatsapp_default_user_id(uid)
        dn = raw_event.get("display_name")
        display_name = (str(dn).strip() if dn else None) or None
        return resolve_channel_user(
            db,
            channel=self.channel,
            channel_user_id=uid,
            default_user_id=default,
            display_name=display_name,
            username=None,
        )

    def normalize_message(self, raw_event: Any, *, app_user_id: str) -> dict[str, Any]:
        if not isinstance(raw_event, dict):
            raise ValueError("whatsapp raw_event must be a dict")
        from_id = (raw_event.get("from") or "").strip()
        text = (raw_event.get("text") or "").strip()
        mid = (raw_event.get("message_id") or "").strip() or None
        wsid = f"whatsapp:{from_id}"[:64]
        return {
            "channel": self.channel,
            "channel_user_id": from_id,
            "user_id": app_user_id,
            "app_user_id": app_user_id,
            "message": text,
            "text": text,
            "attachments": [],
            "metadata": {
                "channel_message_id": mid,
                "channel_thread_id": None,
                "channel_chat_id": from_id,
                "username": None,
                "display_name": raw_event.get("display_name"),
                "update_id": mid,
                "web_session_id": wsid,
            },
        }

    def send_message(self, db: Session, user_id: str, message: str) -> None:
        row = db.scalar(
            select(ChannelUser).where(
                ChannelUser.channel == "whatsapp",
                ChannelUser.user_id == user_id,
            )
        )
        if not row:
            raise ValueError("No WhatsApp channel mapping for this user_id")
        send_whatsapp_text(
            to_wa_id=row.channel_user_id,
            body=message,
            rate_limit_user_id=user_id,
        )


_whatsapp_adapter: WhatsAppAdapter | None = None


def get_whatsapp_adapter() -> WhatsAppAdapter:
    global _whatsapp_adapter
    if _whatsapp_adapter is None:
        _whatsapp_adapter = WhatsAppAdapter()
    return _whatsapp_adapter
