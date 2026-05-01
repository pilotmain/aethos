"""Slack Events API adapter — identity + normalization for Channel Gateway."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.channel_gateway.base import ChannelAdapter
from app.services.channel_gateway.identity import resolve_channel_user

_SLACK_MENTION = re.compile(r"<@[^>]+>")


def slack_default_app_user_id(slack_user_id: str) -> str:
    """Stable Nexa id for a Slack user (distinct from `tg_*`)."""
    su = (slack_user_id or "").strip()
    return f"slack_{su}" if su else "slack_unknown"


class SlackAdapter(ChannelAdapter):
    channel = "slack"

    def resolve_app_user_id(self, db: Session, raw_event: Any) -> str:
        """
        raw_event: ``{"event": slack_message_event_dict, "team_id": str | None}``
        """
        ev = raw_event.get("event") if isinstance(raw_event, dict) else None
        if not isinstance(ev, dict):
            raise ValueError("Slack raw_event missing event dict")
        uid_slack = ev.get("user")
        if not uid_slack:
            raise ValueError("Slack message event missing user")
        default_uid = slack_default_app_user_id(str(uid_slack))
        display_name = None
        profile = ev.get("user_profile")
        if isinstance(profile, dict):
            real = (profile.get("real_name") or profile.get("display_name") or "").strip()
            if real:
                display_name = real
        return resolve_channel_user(
            db,
            channel=self.channel,
            channel_user_id=str(uid_slack).strip(),
            default_user_id=default_uid,
            display_name=display_name,
            username=None,
        )

    def normalize_message(self, raw_event: Any, *, app_user_id: str) -> dict[str, Any]:
        ev = raw_event.get("event") if isinstance(raw_event, dict) else None
        if not isinstance(ev, dict):
            raise ValueError("Slack raw_event missing event dict")
        team_id = (raw_event.get("team_id") if isinstance(raw_event, dict) else None) or ""
        text = ev.get("text") or ""
        if isinstance(text, str):
            text = _SLACK_MENTION.sub("", text).strip()
        ch = str(ev.get("channel") or "").strip()
        ts = str(ev.get("ts") or "").strip()
        thread_ts = ev.get("thread_ts")
        thread_id = str(thread_ts).strip() if thread_ts else None
        wsid = f"slack:{team_id}:{ch}" if ch else "slack:default"
        ch_uid = str(ev.get("user") or "").strip() or None
        return {
            "channel": self.channel,
            "channel_user_id": ch_uid,
            "user_id": app_user_id,
            "app_user_id": app_user_id,
            "message": text,
            "text": text,
            "attachments": [],
            "metadata": {
                "channel_message_id": ts or None,
                "channel_chat_id": ch or None,
                "channel_thread_id": thread_id,
                "username": None,
                "display_name": None,
                "update_id": ts,
                "web_session_id": wsid[:64],
                "slack_team_id": str(team_id) if team_id else None,
            },
        }

    def verify_signature(self, request: Any) -> bool:
        del request
        return True


_slack_adapter: SlackAdapter | None = None


def get_slack_adapter() -> SlackAdapter:
    global _slack_adapter
    if _slack_adapter is None:
        _slack_adapter = SlackAdapter()
    return _slack_adapter
