"""Phase 49 — soften robotic LLM phrasing and bound reply length (natural UX layer)."""

from __future__ import annotations

import re

# Default cap keeps Telegram/web payloads reasonable without clipping normal replies.
_DEFAULT_MAX_CHARS = 14_000

_ROBOTIC_OPENERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?is)^As an AI(?: language model| assistant)?,?\s*"), ""),
    (re.compile(r"(?is)^I(?:'m| am) an AI[^.\n]{0,120}\.\s*"), ""),
    (re.compile(r"(?is)^Based on (?:the )?(?:information|context|details)[^.]{0,160}\.\s*"), ""),
    (re.compile(r"(?is)^(?:In summary|To summarize|Overall),?\s*"), ""),
)


def humanize_response(text: str) -> str:
    """Soften mechanical phrasing; preserve markdown and code fences."""
    if not text or not str(text).strip():
        return text
    t = str(text)
    for rx, repl in _ROBOTIC_OPENERS:
        t = rx.sub(repl, t, count=1)
    # Avoid walls of blank lines (common templated output)
    t = re.sub(r"\n{4,}", "\n\n", t)
    return t.strip()


def minimize_response_length(
    text: str,
    *,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    """Trim only when clearly overlong; prefer paragraph boundaries."""
    if not text or len(text) <= max_chars:
        return text
    window = text[:max_chars]
    cut = window.rfind("\n\n")
    if cut > max_chars // 3:
        return text[:cut].rstrip() + "\n\n…"
    return text[: max_chars - 1].rstrip() + "…"


__all__ = ["humanize_response", "minimize_response_length"]
