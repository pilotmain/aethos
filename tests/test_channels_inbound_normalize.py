# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Multi-channel :class:`~app.channels.base.InboundMessage` normalizers."""

from __future__ import annotations

import pytest

from app.channels.inbound_normalize import (
    slack_message_event_to_inbound,
    twilio_whatsapp_form_to_inbound,
)
from app.services.channel_gateway.whatsapp_twilio import is_twilio_whatsapp_from, twilio_form_to_whatsapp_raw_event


def test_slack_message_event_to_inbound() -> None:
    body = {
        "team_id": "T1",
        "event": {"type": "message", "user": "U123", "channel": "C999", "text": "hello"},
    }
    m = slack_message_event_to_inbound(body)
    assert m is not None
    assert m.channel == "slack"
    assert m.user_id == "U123"
    assert m.chat_id == "C999"
    assert m.text == "hello"


def test_slack_message_event_to_inbound_missing_user() -> None:
    assert slack_message_event_to_inbound({"event": {"channel": "C1", "text": "x"}}) is None


def test_twilio_whatsapp_raw_and_inbound() -> None:
    form = {
        "From": "whatsapp:+15551234567",
        "To": "whatsapp:+15557654321",
        "Body": "ping",
        "MessageSid": "SMabc",
    }
    raw = twilio_form_to_whatsapp_raw_event(form)
    assert raw["from"] == "15551234567"
    assert raw["text"] == "ping"
    inv = twilio_whatsapp_form_to_inbound(form)
    assert inv.channel == "whatsapp"
    assert inv.user_id == "15551234567"
    assert inv.text == "ping"


def test_is_twilio_whatsapp_from() -> None:
    assert is_twilio_whatsapp_from("whatsapp:+1")
    assert not is_twilio_whatsapp_from("+15551234567")


def test_twilio_whatsapp_rejects_plain_sms_from() -> None:
    with pytest.raises(ValueError, match="not a Twilio WhatsApp"):
        twilio_form_to_whatsapp_raw_event({"From": "+15551234567", "Body": "x"})
