# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Sensitive-data redaction for log lines (tokens, URL credentials, common API keys).

Applied via :class:`RedactingFormatter` from :func:`app.services.logging.logger.configure_logging`
and :func:`redact_sensitive_data` is also used by :class:`~app.services.logging.json_formatter.NexaJsonFormatter`.

Patterns are conservative (minimum lengths) to avoid mangling normal prose.
"""

from __future__ import annotations

import logging
import re

_SECRET_PLACEHOLDER = "xxxxx"

# --- Telegram: HTTP API paths use the full token glued after "bot", e.g.
# https://api.telegram.org/bot123456789:AAH.../getMe (httpx / python-telegram-bot).
_TELEGRAM_BOT_URL_TOKEN = re.compile(
    r"(?i)(https?://api\.telegram\.org/bot)(\d{6,16}:[A-Za-z0-9_-]{25,})(?=[/?#]|$)"
)
_TELEGRAM_BOT_PATH_TOKEN = re.compile(
    r"(?i)(/bot)(\d{6,16}:[A-Za-z0-9_-]{25,})(?=[/?#]|$)"
)
_TELEGRAM_BOT_TOKEN_STANDALONE = re.compile(
    r"(?<![A-Za-z0-9])(\d{6,16}):([A-Za-z0-9_-]{25,})(?![A-Za-z0-9])"
)

# --- URL userinfo: scheme://user:password@host (database URLs, basic auth in errors).
_URL_WITH_CREDENTIALS = re.compile(
    r"(?i)([a-z][a-z0-9+.-]*://)([^/\s?#]+):([^@\s/?#]+)(@)"
)

# --- API / cloud tokens (high confidence, used elsewhere e.g. ops_executor / privacy gate).
_OPENAI_SK = re.compile(r"sk-[A-Za-z0-9]{10,}")
_BEARER = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~-]{10,}")
_GITHUB_PAT = re.compile(r"github_pat_[A-Za-z0-9_]{20,}")
_NPM_TOKEN = re.compile(r"npm_[A-Za-z0-9]{30,}")
_SLACK_TOKEN = re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")
_AWS_ACCESS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
# JWT-shaped blobs (Authorization headers, OAuth responses accidentally logged).
_JWT_LIKE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)
# KEY=value / KEY: value for obvious secret names (value must be non-trivial length).
_KV_SECRET = re.compile(
    r'(?i)\b(api_?key|client_secret|access_token|refresh_token|auth_token|password|secret)\s*[:=]\s*(\S{8,})'
)


def redact_sensitive_data(message: str) -> str:
    """Redact secrets and common credential patterns from a log line or JSON string."""
    if not message:
        return message
    out = message

    out = _URL_WITH_CREDENTIALS.sub(rf"\1\2:{_SECRET_PLACEHOLDER}\4", out)

    out = _TELEGRAM_BOT_URL_TOKEN.sub(rf"\1{_SECRET_PLACEHOLDER}", out)
    out = _TELEGRAM_BOT_PATH_TOKEN.sub(rf"\1{_SECRET_PLACEHOLDER}", out)
    out = _TELEGRAM_BOT_TOKEN_STANDALONE.sub(rf"\1:{_SECRET_PLACEHOLDER}", out)

    out = _OPENAI_SK.sub(_SECRET_PLACEHOLDER, out)
    out = _BEARER.sub(f"Bearer {_SECRET_PLACEHOLDER}", out)
    out = _GITHUB_PAT.sub(_SECRET_PLACEHOLDER, out)
    out = _NPM_TOKEN.sub(_SECRET_PLACEHOLDER, out)
    out = _SLACK_TOKEN.sub(_SECRET_PLACEHOLDER, out)
    out = _AWS_ACCESS_KEY.sub(_SECRET_PLACEHOLDER, out)
    out = _JWT_LIKE.sub(_SECRET_PLACEHOLDER, out)
    out = _KV_SECRET.sub(rf"\1={_SECRET_PLACEHOLDER}", out)

    return out


class RedactingFormatter(logging.Formatter):
    """Wraps a standard formatter and redacts secrets from the final line."""

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        return redact_sensitive_data(line)
