"""Twilio SMS adapter — identity + normalization for Channel Gateway (Phase 10)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel_user import ChannelUser
from app.services.channel_gateway.base import ChannelAdapter
from app.services.channel_gateway.identity import resolve_channel_user
from app.services.channel_gateway.sms_send import normalize_to_address, send_sms_text

_DIGITS_ONLY = re.compile(r"^\d{4,20}$")


def normalize_twilio_e164(address: str) -> str:
    """Canonical ``+`` + digits for ``channel_user_id`` / metadata."""
    d = "".join(c for c in (address or "") if c.isdigit())
    if not _DIGITS_ONLY.match(d):
        raise ValueError("invalid SMS phone number")
    return f"+{d}"


def sms_default_user_id(address: str) -> str:
    """Stable Nexa id ``sms_<digits>`` (distinct from ``wa_*``, ``tg_*``, …)."""
    d = "".join(c for c in (address or "") if c.isdigit())
    if len(d) < 4 or len(d) > 20:
        raise ValueError("invalid SMS phone for user id")
    return f"sms_{d}"


def twilio_form_to_raw_event(form: dict[str, str]) -> dict[str, Any]:
    """Map Twilio inbound webhook fields to adapter ``raw_event``."""
    return {
        "From": form.get("From") or "",
        "To": form.get("To") or "",
        "Body": form.get("Body") or "",
        "MessageSid": form.get("MessageSid") or form.get("SmsSid") or "",
        "SmsSid": form.get("SmsSid") or "",
        "AccountSid": form.get("AccountSid") or "",
        "provider": "twilio",
    }


class SMSAdapter(ChannelAdapter):
    channel = "sms"

    def resolve_app_user_id(self, db: Session, raw_event: Any) -> str:
        if not isinstance(raw_event, dict):
            raise ValueError("sms raw_event must be a dict")
        frm = normalize_twilio_e164(str(raw_event.get("From") or ""))
        default_uid = sms_default_user_id(frm)
        return resolve_channel_user(
            db,
            channel=self.channel,
            channel_user_id=frm,
            default_user_id=default_uid,
            display_name=None,
            username=None,
        )

    def normalize_message(self, raw_event: Any, *, app_user_id: str) -> dict[str, Any]:
        if not isinstance(raw_event, dict):
            raise ValueError("sms raw_event must be a dict")
        frm = normalize_twilio_e164(str(raw_event.get("From") or ""))
        to_raw = str(raw_event.get("To") or "").strip()
        to_canon: str | None
        if to_raw:
            try:
                to_canon = normalize_twilio_e164(to_raw)
            except ValueError:
                to_canon = None
        else:
            to_canon = None
        body = (raw_event.get("Body") or "").strip()
        mid = (raw_event.get("MessageSid") or raw_event.get("SmsSid") or "").strip() or None
        digits = "".join(c for c in frm if c.isdigit())
        wsid = f"sms:{digits}"[:64]
        return {
            "channel": self.channel,
            "channel_user_id": frm,
            "user_id": app_user_id,
            "app_user_id": app_user_id,
            "message": body,
            "text": body,
            "attachments": [],
            "metadata": {
                "channel_message_id": mid,
                "channel_thread_id": None,
                "channel_chat_id": to_canon or None,
                "sms_from": frm,
                "sms_to": to_canon or None,
                "provider": str(raw_event.get("provider") or "twilio"),
                "update_id": mid,
                "web_session_id": wsid,
            },
        }

    def send_message(self, db: Session, user_id: str, message: str) -> None:
        row = db.scalar(
            select(ChannelUser).where(
                ChannelUser.channel == "sms",
                ChannelUser.user_id == user_id,
            )
        )
        if not row:
            raise ValueError("No SMS channel mapping for this user_id")
        send_sms_text(to_e164=row.channel_user_id, body=message, rate_limit_user_id=user_id)


_sms_adapter: SMSAdapter | None = None


def get_sms_adapter() -> SMSAdapter:
    global _sms_adapter
    if _sms_adapter is None:
        _sms_adapter = SMSAdapter()
    return _sms_adapter
