"""Detect accidental secret pastes before host executor / path routing (Phase 51+ routing hardening)."""

from __future__ import annotations

import re

# Assignment-style env secrets (not exhaustive — extend as needed).
_RE_SECRET_ASSIGN = re.compile(
    r"(?i)\b(OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|"
    r"GITHUB_TOKEN|GH_TOKEN|SLACK_BOT_TOKEN|TELEGRAM_BOT_TOKEN|STRIPE_SECRET|DATABASE_URL|"
    r"NEXA_SECRET_KEY|GOOGLE_API_KEY)\s*="
)
_RE_SK_OPENAI = re.compile(r"(?<![\w/])(sk-[a-zA-Z0-9]{10,})(?![\w/-])")
_RE_SK_ANTHROPIC = re.compile(r"(?<![\w/])(sk-ant-[a-zA-Z0-9-]{10,})(?![\w/-])")


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


def secret_paste_chat_reply() -> str:
    return (
        "Don’t paste API keys or secrets in chat. If you posted a real key, rotate it in the provider "
        "console now. Add keys with `/key set …` or host environment variables — not in messages."
    )


__all__ = ["secret_paste_chat_reply", "user_message_contains_inline_secret"]
