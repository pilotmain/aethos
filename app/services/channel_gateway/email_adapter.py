"""Inbound email adapter — identity + normalization for Channel Gateway (Phase 7)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel_user import ChannelUser
from app.services.channel_gateway.base import ChannelAdapter
from app.services.channel_gateway.email_links import format_email_permission_text
from app.services.channel_gateway.email_smtp import send_smtp_email
from app.services.channel_gateway.identity import resolve_channel_user

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_addr(addr: str) -> str:
    s = (addr or "").strip().lower()
    if not s or not _EMAIL_RE.match(s):
        raise ValueError("Invalid or missing email address")
    return s


def email_default_user_id(addr: str) -> str:
    """
    Stable Nexa id for an email address (distinct from ``tg_*`` / ``slack_*`` / ``web_*``).
    Truncated hash keeps ``user_id`` within the 64-char DB limit.
    """
    norm = _normalize_addr(addr)
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]
    return f"em_{h}"


class EmailAdapter(ChannelAdapter):
    channel = "email"

    def resolve_app_user_id(self, db: Session, raw_event: Any) -> str:
        if not isinstance(raw_event, dict):
            raise ValueError("email raw_event must be a dict")
        addr = raw_event.get("from") or raw_event.get("from_address")
        norm = _normalize_addr(str(addr))
        default_uid = email_default_user_id(norm)
        return resolve_channel_user(
            db,
            channel=self.channel,
            channel_user_id=norm,
            default_user_id=default_uid,
            display_name=None,
            username=norm,
        )

    def normalize_message(self, raw_event: Any, *, app_user_id: str) -> dict[str, Any]:
        if not isinstance(raw_event, dict):
            raise ValueError("email raw_event must be a dict")
        addr = _normalize_addr(str(raw_event.get("from") or raw_event.get("from_address") or ""))
        text = (raw_event.get("text") or raw_event.get("body") or "").strip()
        if not text and (raw_event.get("subject") or ""):
            text = (raw_event.get("subject") or "").strip()
        subj = (raw_event.get("subject") or "").strip()
        mid = (raw_event.get("message_id") or raw_event.get("messageId") or "").strip() or None
        th = (raw_event.get("thread_id") or raw_event.get("threadId") or "").strip() or None
        wsid = f"email:{th}" if th else f"email:{addr}"
        return {
            "channel": self.channel,
            "channel_user_id": addr,
            "user_id": app_user_id,
            "app_user_id": app_user_id,
            "message": text,
            "text": text,
            "attachments": list(raw_event.get("attachments") or []),
            "metadata": {
                "channel_message_id": mid,
                "channel_thread_id": th,
                "subject": subj,
                "email_from": addr,
                "update_id": mid,
                "web_session_id": wsid[:64],
            },
        }

    def send_message(
        self,
        db: Session,
        user_id: str,
        message: str,
        *,
        subject: str = "Nexa",
    ) -> None:
        row = db.scalar(
            select(ChannelUser).where(
                ChannelUser.channel == "email",
                ChannelUser.user_id == user_id,
            )
        )
        if not row:
            raise ValueError("No email channel mapping for this user_id")
        send_smtp_email(
            to_addr=row.channel_user_id,
            subject=subject,
            body=message,
            rate_limit_user_id=user_id,
        )

    def send_permission_card(self, db: Session, user_id: str, payload: dict[str, Any]) -> None:
        """
        Email cannot embed interactive buttons; send a single message with secure approval links.
        """
        try:
            pid = int(
                str(payload.get("permission_request_id") or payload.get("permission_id") or "0")
            )
        except (TypeError, ValueError):
            pid = 0
        if not pid:
            raise ValueError("permission payload missing permission id")
        reason = (payload.get("reason") or payload.get("message") or "").strip()
        links = format_email_permission_text(pid, user_id)
        body = (f"{reason}\n\n" if reason else "") + links
        self.send_message(db, user_id, body.strip(), subject="Nexa — permission required")


_email_adapter: EmailAdapter | None = None


def get_email_adapter() -> EmailAdapter:
    global _email_adapter
    if _email_adapter is None:
        _email_adapter = EmailAdapter()
    return _email_adapter
