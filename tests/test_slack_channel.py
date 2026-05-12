# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 12.1 — Slack channel helpers (no live Slack API)."""

from __future__ import annotations

from unittest.mock import patch

from app.channels.slack.adapter import SlackSocketNexaChannel
from app.channels.slack.message_converter import (
    bolt_body_to_raw_event,
    reaction_summary_text,
    synthetic_message_event_from_command,
)


def test_bolt_body_to_raw_event_maps_team() -> None:
    body = {
        "team_id": "T09",
        "event": {"type": "message", "user": "U1", "text": "hi", "channel": "C1"},
    }
    raw = bolt_body_to_raw_event(body)
    assert raw["team_id"] == "T09"
    assert raw["event"]["text"] == "hi"


def test_synthetic_command_event() -> None:
    cmd = {
        "user_id": "U9",
        "channel_id": "C9",
        "team_id": "T9",
        "text": "help",
    }
    ev = synthetic_message_event_from_command(cmd)
    assert ev["user"] == "U9"
    assert ev["channel"] == "C9"
    assert ev["text"] == "help"


def test_reaction_summary_text_shape() -> None:
    ev = {
        "user": "U1",
        "reaction": "thumbsup",
        "item": {"type": "message", "channel": "C1", "ts": "123.456"},
    }
    s = reaction_summary_text(ev)
    assert "thumbsup" in s
    assert "C1" in s


def test_slack_socket_channel_disabled_without_tokens() -> None:
    ch = SlackSocketNexaChannel()
    with patch("app.channels.slack.adapter.get_settings") as m:
        m.return_value.nexa_slack_enabled = True
        m.return_value.slack_bot_token = ""
        m.return_value.slack_app_token = ""
        assert ch.enabled is False
