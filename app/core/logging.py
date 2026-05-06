"""
Sensitive-data redaction for log lines (Telegram bot tokens, etc.).

Applied via :class:`RedactingFormatter` from :func:`app.services.logging.logger.configure_logging`.
"""

from __future__ import annotations

import logging
import re

# Telegram HTTP API paths use the full token glued after "bot" (no delimiter), e.g.
#   https://api.telegram.org/bot123456789:AAH.../getMe
# A naive "(?<![A-Za-z0-9])<id>:<secret>" pattern misses that case because the id is
# preceded by "t" from "bot".
_TELEGRAM_BOT_URL_TOKEN = re.compile(
    r"(?i)(https?://api\.telegram\.org/bot)(\d{6,16}:[A-Za-z0-9_-]{25,})(?=[/?#]|$)"
)
# Same path segment when logged as a relative path only.
_TELEGRAM_BOT_PATH_TOKEN = re.compile(
    r"(?i)(/bot)(\d{6,16}:[A-Za-z0-9_-]{25,})(?=[/?#]|$)"
)
# Standalone token text (not immediately after a letter/digit that would indicate /bot<id> glue).
_TELEGRAM_BOT_TOKEN_STANDALONE = re.compile(
    r"(?<![A-Za-z0-9])(\d{6,16}):([A-Za-z0-9_-]{25,})(?![A-Za-z0-9])"
)

_SECRET_PLACEHOLDER = "xxxxx"


def redact_sensitive_data(message: str) -> str:
    """Redact secrets from a single log line or JSON payload string."""
    if not message:
        return message
    out = message
    out = _TELEGRAM_BOT_URL_TOKEN.sub(rf"\1{_SECRET_PLACEHOLDER}", out)
    out = _TELEGRAM_BOT_PATH_TOKEN.sub(rf"\1{_SECRET_PLACEHOLDER}", out)
    out = _TELEGRAM_BOT_TOKEN_STANDALONE.sub(rf"\1:{_SECRET_PLACEHOLDER}", out)
    return out


class RedactingFormatter(logging.Formatter):
    """Wraps a standard formatter and redacts secrets from the final line."""

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        return redact_sensitive_data(line)
