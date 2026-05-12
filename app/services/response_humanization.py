# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

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


_RE_FILLER_PARA = re.compile(
    r"(?is)^(I hope this helps\.?|Feel free to ask.*|Let me know if you (have )?any questions\.?)\s*$"
)


def enforce_precision(text: str) -> str:
    """Drop duplicate paragraphs and chatty filler lines (Phase 50 precision layer)."""
    if not (text and text.strip()):
        return text
    blocks = re.split(r"\n\s*\n+", text)
    out: list[str] = []
    seen_norm: set[str] = set()
    for block in blocks:
        raw = block.strip()
        if not raw:
            continue
        if _RE_FILLER_PARA.match(raw):
            continue
        norm = re.sub(r"\s+", " ", raw.lower()).rstrip(".!? ")
        if len(norm) >= 8 and norm in seen_norm:
            continue
        seen_norm.add(norm)
        out.append(raw)
    return "\n\n".join(out).strip()


__all__ = ["enforce_precision", "humanize_response", "minimize_response_length"]
