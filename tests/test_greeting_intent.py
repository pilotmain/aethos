# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.gateway.greeting_replies import greeting_reply_for_text
from app.services.host_executor_intent import parse_greeting_intent
from app.services.intent_classifier import get_intent, is_greeting_message


def test_is_greeting_message_punctuation() -> None:
    assert is_greeting_message("Hi")
    assert is_greeting_message("Hi!")
    assert is_greeting_message("Hello there")
    assert is_greeting_message("Hey")
    assert is_greeting_message("Good morning")
    assert not is_greeting_message("Hi, create a marketing agent for me")
    assert not is_greeting_message("what is the meaning of hello")


def test_get_intent_greeting_before_general() -> None:
    assert get_intent("Hi!") == "greeting"
    assert get_intent("Hello") == "greeting"


def test_greeting_reply_contains_aethos() -> None:
    assert "AethOS" in greeting_reply_for_text("Hi")
    assert "👋" in greeting_reply_for_text("Hello")


def test_parse_greeting_intent_alias() -> None:
    assert parse_greeting_intent("Hey") is True
    assert parse_greeting_intent("deploy to prod") is False
