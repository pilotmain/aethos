"""Inline secret detection before host/path routing."""

from __future__ import annotations

from app.services.input_secret_guard import user_message_contains_inline_secret


def test_detects_openai_assignment() -> None:
    assert user_message_contains_inline_secret("OPENAI_API_KEY=sk-1234567890abcdefghij")


def test_detects_sk_token_shape() -> None:
    assert user_message_contains_inline_secret("here is my key sk-123456789012345678901234")


def test_clean_general_chat_negative() -> None:
    assert not user_message_contains_inline_secret("debug Spring OIDC on EKS with MongoDB")


def test_anthropic_sk_ant() -> None:
    t = "sk-ant-api03-12345678901234567890123456789012"
    assert user_message_contains_inline_secret(f"key {t}")
