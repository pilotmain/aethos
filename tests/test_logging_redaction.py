"""Redaction of Telegram-style bot tokens in log output."""

from __future__ import annotations

from app.core.logging import redact_sensitive_data


def test_redact_telegram_bot_token_shape() -> None:
    raw = "Connecting with 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopQRSTUVWXYZ0123456789"
    out = redact_sensitive_data(raw)
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in out
    assert "[REDACTED]" in out
    assert "123456789:[REDACTED]" in out


def test_redact_short_strings_untouched() -> None:
    """Avoid redacting innocent colon-separated pairs."""
    s = "ratio 12:34 in CSV"
    assert redact_sensitive_data(s) == s
