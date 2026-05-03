"""Detect accidental secret pastes before host executor / path routing (Phase 51+ routing hardening)."""

from __future__ import annotations

import re

# Assignment-style env secrets (not exhaustive — extend as needed).
_RE_SECRET_ASSIGN = re.compile(
    r"(?i)\b(OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|"
    r"GITHUB_TOKEN|GH_TOKEN|SLACK_BOT_TOKEN|TELEGRAM_BOT_TOKEN|STRIPE_SECRET|DATABASE_URL|"
    r"NEXA_SECRET_KEY|GOOGLE_API_KEY|RAILWAY_TOKEN|RAILWAY_API_TOKEN)\s*="
)
_RE_SK_OPENAI = re.compile(r"(?<![\w/])(sk-[a-zA-Z0-9]{10,})(?![\w/-])")
_RE_SK_ANTHROPIC = re.compile(r"(?<![\w/])(sk-ant-[a-zA-Z0-9-]{10,})(?![\w/-])")

# Railway / deploy-shaped paste lines (values must never be echoed or stored).
_RE_RAILWAY_ENV_ASSIGN = re.compile(r"(?i)\b(RAILWAY_TOKEN|RAILWAY_API_TOKEN)\s*=")
_RE_SOFT_CRED_ASSIGN = re.compile(
    r"(?i)(?:"
    r"\bapi\s*key\s*=|"
    r"\brailway\s+api\s+key\s*=|"
    r"\brailway\s*(?:api\s*)?token\s*=|"
    r"\brailway\s+token\s*="
    r")"
)


def user_message_contains_inline_secret(text: str) -> bool:
    """True when the message likely contains a credential (should not drive filesystem routing)."""
    t = text or ""
    if len(t) > 50_000:
        t = t[:50_000]
    if _RE_SECRET_ASSIGN.search(t):
        return True
    if _RE_SK_OPENAI.search(t) or _RE_SK_ANTHROPIC.search(t):
        return True
    return False


def user_message_contains_railway_credential_paste(text: str) -> bool:
    """
    True when the user likely pasted a Railway/API token in chat (secure-setup flow).

    Triggers on ``RAILWAY_TOKEN=``, ``railway api key =``, etc., or Railway context + assignment patterns.
    """
    t = text or ""
    if len(t) > 50_000:
        t = t[:50_000]
    tl = t.lower()
    if _RE_RAILWAY_ENV_ASSIGN.search(t):
        return True
    if user_message_contains_inline_secret(t) and "railway" in tl:
        return True
    if not re.search(r"(?i)\brailway\b", t):
        return False
    if _RE_SOFT_CRED_ASSIGN.search(t):
        return True
    # "token" / "api key" near an equals sign within Railway-context prose
    if re.search(r"(?i)\brailway\b.{0,200}(?:token|api\s*key)\s*=", t):
        return True
    if re.search(r"(?i)(?:token|api\s*key)\s*=.{0,120}\brailway\b", t):
        return True
    return False


def secret_paste_chat_reply() -> str:
    return (
        "Don’t paste API keys or secrets in chat. If you posted a real key, rotate it in the provider "
        "console now. Add keys with `/key set …` or host environment variables — not in messages."
    )


__all__ = [
    "secret_paste_chat_reply",
    "user_message_contains_inline_secret",
    "user_message_contains_railway_credential_paste",
]
