"""Slack Block Kit for permission cards (interactions call Nexa grant/deny, not raw URLs)."""

from __future__ import annotations

import json
from typing import Any

from app.services.access_permissions import GRANT_MODE_ONCE, GRANT_MODE_SESSION


def _action_value(permission_id: int, action: str) -> str:
    return json.dumps(
        {"permission_id": int(permission_id), "action": action},
        separators=(",", ":"),
    )[:2000]


def permission_blocks(*, pr: dict[str, Any], channel_for_reply: str) -> list[dict[str, Any]]:
    """
    Build blocks for a pending permission. Button `value` encodes permission_id + action
    for `/api/v1/slack/interactions` (signature-verified; resolves owner via ChannelUser).
    """
    _ = channel_for_reply  # reserved for future (e.g. link unfurl)
    try:
        pid = int(str(pr.get("permission_request_id") or pr.get("permission_id") or "0"))
    except (TypeError, ValueError):
        pid = 0
    reason = (pr.get("reason") or pr.get("message") or "Nexa needs permission for this action.").strip()
    scope = str(pr.get("scope") or "—")[:120]
    target = str(pr.get("target") or "—")[:500]
    risk = str(pr.get("risk_level") or "—")[:64]
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔐 *Permission required*\n*Scope:* `{scope}`\n*Target:* `{target}`\n*Risk:* {risk}\n{reason}",
            },
        },
        {
            "type": "actions",
            "block_id": f"nexa_perm_{pid}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Allow once"},
                    "style": "primary",
                    "action_id": "nexa_perm_approve_once",
                    "value": _action_value(pid, "approve_once"),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Allow for session"},
                    "action_id": "nexa_perm_approve_session",
                    "value": _action_value(pid, "approve_session"),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Deny"},
                    "style": "danger",
                    "action_id": "nexa_perm_deny",
                    "value": _action_value(pid, "deny"),
                },
            ],
        },
    ]


def grant_mode_for_action(action: str) -> str:
    if action == "approve_session":
        return GRANT_MODE_SESSION
    return GRANT_MODE_ONCE
