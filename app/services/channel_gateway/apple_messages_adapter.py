"""Apple Messages for Business (provider) — identity + normalization for Channel Gateway (Phase 11)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel_user import ChannelUser
from app.services.channel_gateway.base import ChannelAdapter
from app.services.channel_gateway.identity import resolve_channel_user
from app.services.channel_gateway.apple_messages_send import send_apple_message_text

# Provider-defined customer id; stable alphanumerics, underscore, hyphen, colon.
_CUSTOMER_RE = re.compile(r"^[A-Za-z0-9_\-:]{1,128}$")


def _normalize_customer_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s or not _CUSTOMER_RE.match(s):
        raise ValueError("invalid Apple Messages customer_id")
    return s


def apple_messages_default_user_id(customer_id: str) -> str:
    """Stable Nexa id ``am_<hex>`` (distinct from ``em_*``, ``sms_*``, …)."""
    norm = _normalize_customer_id(customer_id)
    h = hashlib.sha256(f"apple_messages:{norm}".encode("utf-8")).hexdigest()[:32]
    return f"am_{h}"


def json_payload_to_raw_event(body: dict[str, Any]) -> dict[str, Any]:
    """Map generic provider JSON to adapter ``raw_event``."""
    return {
        "provider": str(body.get("provider") or "apple_business_messages"),
        "customer_id": str(body.get("customer_id") or ""),
        "conversation_id": str(body.get("conversation_id") or ""),
        "message_id": str(body.get("message_id") or ""),
        "text": str(body.get("text") or ""),
        "timestamp": str(body.get("timestamp") or ""),
    }


class AppleMessagesAdapter(ChannelAdapter):
    channel = "apple_messages"

    def resolve_app_user_id(self, db: Session, raw_event: Any) -> str:
        if not isinstance(raw_event, dict):
            raise ValueError("apple_messages raw_event must be a dict")
        cid = _normalize_customer_id(str(raw_event.get("customer_id") or ""))
        default_uid = apple_messages_default_user_id(cid)
        return resolve_channel_user(
            db,
            channel=self.channel,
            channel_user_id=cid,
            default_user_id=default_uid,
            display_name=None,
            username=None,
        )

    def normalize_message(self, raw_event: Any, *, app_user_id: str) -> dict[str, Any]:
        if not isinstance(raw_event, dict):
            raise ValueError("apple_messages raw_event must be a dict")
        cid = _normalize_customer_id(str(raw_event.get("customer_id") or ""))
        conv = (raw_event.get("conversation_id") or "").strip() or None
        mid = (raw_event.get("message_id") or "").strip() or None
        body = (raw_event.get("text") or "").strip()
        prov = (raw_event.get("provider") or "apple_business_messages").strip()
        wsid = f"apple_messages:{cid}"[:64]
        chat_id = (conv or cid)
        return {
            "channel": self.channel,
            "channel_user_id": cid,
            "user_id": app_user_id,
            "app_user_id": app_user_id,
            "message": body,
            "text": body,
            "attachments": [],
            "metadata": {
                "provider": prov,
                "channel_message_id": mid,
                "channel_chat_id": chat_id,
                "channel_thread_id": chat_id,
                "customer_id": cid,
                "update_id": mid,
                "web_session_id": wsid,
            },
        }

    def send_message(self, db: Session, user_id: str, message: str) -> None:
        row = db.scalar(
            select(ChannelUser).where(
                ChannelUser.channel == "apple_messages",
                ChannelUser.user_id == user_id,
            )
        )
        if not row:
            raise ValueError("No Apple Messages channel mapping for this user_id")
        send_apple_message_text(
            to=row.channel_user_id,
            body=message,
            rate_limit_user_id=user_id,
        )


_am_adapter: AppleMessagesAdapter | None = None


def get_apple_messages_adapter() -> AppleMessagesAdapter:
    global _am_adapter
    if _am_adapter is None:
        _am_adapter = AppleMessagesAdapter()
    return _am_adapter
