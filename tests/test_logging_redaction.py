# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Redaction of Telegram-style bot tokens in log output."""

from __future__ import annotations

from app.core.logging import redact_sensitive_data


def test_redact_telegram_bot_token_shape() -> None:
    raw = "Connecting with 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopQRSTUVWXYZ0123456789"
    out = redact_sensitive_data(raw)
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in out
    assert "123456789:xxxxx" in out


def test_redact_telegram_api_url_contains_glued_bot_prefix() -> None:
    """URLs use /bot<id>:<secret>/ — the id must still be redacted (secret only → xxxxx)."""
    tok = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopQRSTUVWXYZ0123456789"
    raw = f"HTTP Request: GET https://api.telegram.org/bot{tok}/getMe \"HTTP/1.1 200 OK\""
    out = redact_sensitive_data(raw)
    assert tok not in out
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in out
    assert "https://api.telegram.org/botxxxxx" in out


def test_redact_short_strings_untouched() -> None:
    """Avoid redacting innocent colon-separated pairs."""
    s = "ratio 12:34 in CSV"
    assert redact_sensitive_data(s) == s


def test_redact_database_url_password() -> None:
    raw = "pq failed postgresql+psycopg2://dbuser:MY_SECRET_PASS@127.0.0.1:5434/overwhelm"
    out = redact_sensitive_data(raw)
    assert "MY_SECRET_PASS" not in out
    assert "postgresql+psycopg2://dbuser:xxxxx@127.0.0.1:5434/overwhelm" in out


def test_redact_openai_style_sk() -> None:
    raw = "echo sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUV"
    out = redact_sensitive_data(raw)
    assert "sk-abcdef" not in out
    assert "xxxxx" in out


def test_redact_github_pat_and_kv_assignment() -> None:
    raw = "github_pat_" + "a" * 22 + " api_key=supersecret123456789"
    out = redact_sensitive_data(raw)
    assert "github_pat_" not in out
    assert "api_key=xxxxx" in out


def test_redact_bearer_header_value() -> None:
    raw = "curl -H 'Authorization: Bearer ya29.a0AfH6SMBxYzVeryLongTokenHere012345678901234567890'"
    out = redact_sensitive_data(raw)
    assert "ya29.a0AfH6SMBxYzVeryLongTokenHere" not in out
    assert "Bearer xxxxx" in out
