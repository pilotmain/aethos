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
