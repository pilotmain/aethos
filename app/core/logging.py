"""
Sensitive-data redaction for log lines (Telegram bot tokens, etc.).

Applied via :class:`RedactingFormatter` from :func:`app.services.logging.logger.configure_logging`.
"""

from __future__ import annotations

import logging
import re

# Telegram bot token shape: numeric bot id (typically 8–12 digits), colon, URL-safe secret (long).
_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(\d{8,14}):([A-Za-z0-9_-]{25,})(?![A-Za-z0-9])"
)


def redact_sensitive_data(message: str) -> str:
    """Redact secrets from a single log line or JSON payload string."""
    if not message:
        return message
    out = _TELEGRAM_BOT_TOKEN_PATTERN.sub(r"\1:[REDACTED]", message)
    return out


class RedactingFormatter(logging.Formatter):
    """Wraps a standard formatter and redacts secrets from the final line."""

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        return redact_sensitive_data(line)
