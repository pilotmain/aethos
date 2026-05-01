"""Derive a short chat title from the first user line (no LLM). Used for the web session list."""

from __future__ import annotations

import re


def derive_web_chat_title_from_message(user_text: str) -> str:
    t = (user_text or "").strip()
    if not t or len(t) < 1:
        return "New chat"
    t = re.sub(r"^@[A-Za-z][A-Za-z0-9_]*\s+", "", t, count=1)
    t = re.sub(r"^\s*/[A-Za-z0-9_-]+(?:\s+[^/]*)?\s+", "", t, count=1)
    t = t.replace("\n", " ").strip()
    words = t.split()[:10]
    out = " ".join(words) if words else t[:40]
    if not out:
        return "New chat"
    if len(out) > 40:
        out = out[:37].rstrip() + "…"
    return out
