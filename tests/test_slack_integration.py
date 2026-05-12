# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 42 — Slack gateway ↔ Nexa router bridge."""

from __future__ import annotations

from app.services.channels.slack_bot import slack_inbound_via_gateway


def test_slack_inbound_via_gateway_returns_message_shape(db_session) -> None:
    norm = {
        "channel": "slack",
        "channel_user_id": "U1",
        "user_id": "slack_bridge_u1",
        "app_user_id": "slack_bridge_u1",
        "message": "hello slack bridge",
        "text": "hello slack bridge",
        "metadata": {"web_session_id": "slack:team:CH"},
    }
    env = slack_inbound_via_gateway(db_session, norm)
    assert "message" in env
    assert env.get("permission_required") is None
    assert isinstance(env.get("message"), str)
