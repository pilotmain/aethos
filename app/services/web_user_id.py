"""Validation for the Nexa web API X-User-Id header — reject bot tokens and malformed ids."""
from __future__ import annotations

import re
from typing import Final

# Fixed message: never include client-supplied raw value in API responses.
WEB_USER_ID_INVALID: Final[str] = (
    "Invalid Web User ID. Use a Nexa channel user id "
    "(e.g. tg_<digits>, web_<label>, em_<hex>, slack_<id>, sms_<digits>, wa_<digits>, am_<hex>). "
    "Do not paste a Telegram bot token."
)

_MAX_LEN: Final[int] = 80

# Legacy / mistaken client alias (curl scripts, docs). Canonical Telegram channel id is tg_<digits>.
_TELEGRAM_LEGACY: Final[re.Pattern[str]] = re.compile(r"^telegram_[0-9]{3,20}$")

_TG: Final[re.Pattern[str]] = re.compile(r"^tg_[0-9]{3,20}$")
_WEB: Final[re.Pattern[str]] = re.compile(r"^web_[A-Za-z0-9_-]{1,64}$")
_LOCAL: Final[re.Pattern[str]] = re.compile(r"^local_[A-Za-z0-9_-]{1,64}$")
# Email channel user ids (SHA-256 hex digest slice, max 32 hex chars)
_EM: Final[re.Pattern[str]] = re.compile(r"^em_[a-f0-9]{8,32}$")
# WhatsApp Cloud API — sender id is numeric (wa_<digits>)
_WA: Final[re.Pattern[str]] = re.compile(r"^wa_[0-9]{4,20}$")
# SMS (Twilio) — E.164 digits only after prefix (sms_<digits>)
_SMS: Final[re.Pattern[str]] = re.compile(r"^sms_[0-9]{4,20}$")
# Apple Messages for Business (provider) — am_<hex> (same shape as em_)
_AM: Final[re.Pattern[str]] = re.compile(r"^am_[a-f0-9]{8,32}$")
# Slack — workspace user id after prefix (e.g. slack_U12345ABC)
_SLACK: Final[re.Pattern[str]] = re.compile(r"^slack_[A-Za-z0-9]{1,64}$")


def _normalize_web_user_id_aliases(s: str) -> str:
    """Map informal Telegram ids to canonical ``tg_<digits>`` before pattern validation."""
    if _TELEGRAM_LEGACY.match(s):
        return "tg_" + s[len("telegram_") :]
    # Internal registry scope alias: telegram:<digits> (same digits as tg_<digits> in typical DM flows)
    if s.startswith("telegram:"):
        tail = s[len("telegram:") :]
        if tail.isdigit() and 3 <= len(tail) <= 20:
            return "tg_" + tail
    return s


def validate_web_user_id(raw: str) -> str:
    """
    Return a safe web user id or raise :exc:`ValueError`.

    Accepted: ``tg_<3–20 digits>`` (aliases: ``telegram_<digits>`` or ``telegram:<digits>`` → ``tg_…``),
    ``web_<1–64 safe chars>``, ``local_<1–64 safe chars>``,
    ``em_<8–32 lowercase hex>`` (email channel),
    ``wa_<4–20 digits>`` (WhatsApp), ``sms_<4–20 digits>`` (SMS / Twilio),
    ``am_<8–32 lowercase hex>`` (Apple Messages),
    ``slack_<1–64 alphanumeric>`` (Slack),
    with overall length ≤ 80.
    Rejects empty values, untrimmed whitespace, internal spaces, colons, and disallowed id shapes.
    """
    if not isinstance(raw, str):
        raise ValueError
    s0 = raw
    s = s0.strip()
    if s != s0 or not s:
        raise ValueError
    s = _normalize_web_user_id_aliases(s)
    if any(c.isspace() for c in s):
        raise ValueError
    if len(s) > _MAX_LEN or ":" in s:
        raise ValueError
    if not (
        _TG.match(s)
        or _WEB.match(s)
        or _LOCAL.match(s)
        or _EM.match(s)
        or _WA.match(s)
        or _SMS.match(s)
        or _AM.match(s)
        or _SLACK.match(s)
    ):
        raise ValueError
    return s
