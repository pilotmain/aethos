"""Canned, accurate answers for owner / creator identity (no model guesswork)."""
from __future__ import annotations

import re

from app.services.memory_preferences import get_effective_owner_pronoun

# Align with soul.md; adjust neutral variant when profile has no known pronoun.
MSG_RAYA_MASCULINE = (
    "Raya Ameha Meresa is the creator of Nexa.\n\n"
    "He is building Nexa as a personal execution system that helps people think "
    "clearly and get things done."
)
MSG_RAYA_NEUTRAL = (
    "Raya Ameha Meresa is the creator of Nexa.\n\n"
    "Raya is building Nexa as a personal execution system that helps people think "
    "clearly and get things done."
)


_RE_RAYA_FAQ = re.compile(
    r"(?i)^\s*("
    r"who\s+(is|are|was)\s+raya"
    r"|what\s+is\s+raya"
    r"|tell\s+me\s+about\s+raya"
    r"|what(\s+do|\s+can)\s+you(\s+know)?\s+about\s+raya"
    r")[\s.!?]*$",
)


def is_raya_owner_identity_faq(user_message: str) -> bool:
    t = (user_message or "").strip()
    if not t or len(t) > 160 or "\n" in t:
        return False
    if "raya" not in t.lower():
        return False
    return bool(_RE_RAYA_FAQ.match(t.strip()))


_RE_WHO_CREATED_NEXA = re.compile(
    r"(?is)^\s*who\s+created\s+nexa\s*[?.!]*\s*$",
)
_RE_WHAT_IS_NEXA = re.compile(
    r"(?is)^\s*what\s+is\s+nexa\s*[?.!]*\s*$",
)
_RE_WHO_ARE_YOU = re.compile(
    r"(?is)^\s*who\s+are\s+you\s*[?.!]*\s*$",
)


def try_canned_nexa_product_faq(user_message: str) -> str | None:
    """Short canned answers — no LLM (saves full composer context)."""
    t = (user_message or "").strip()
    if not t or len(t) > 200 or "\n" in t:
        return None
    if _RE_WHO_CREATED_NEXA.match(t):
        return "Nexa was created by **Raya Ameha Meresa**."
    if _RE_WHAT_IS_NEXA.match(t):
        return (
            "Nexa is an **AI execution system**: it helps you think, decide, and get work done — "
            "creating task-focused agents dynamically when tasks need them, with permissioned execution and memory."
        )
    if _RE_WHO_ARE_YOU.match(t):
        return (
            "I’m **Nexa** — the execution layer in this app. I answer plain questions directly and "
            "spin up or route work when you need action, jobs, or missions."
        )
    return None


def try_canned_owner_identity_faq(
    user_message: str,
    *,
    user_preferences: dict[str, str] | None = None,
) -> str | None:
    if not is_raya_owner_identity_faq(user_message):
        return None
    p = (get_effective_owner_pronoun(user_preferences) or "they").lower()
    if p in ("he", "him", "his"):
        return MSG_RAYA_MASCULINE
    if p in ("she", "her", "hers"):
        return (
            "Raya Ameha Meresa is the creator of Nexa.\n\n"
            "She is building Nexa as a personal execution system that helps people think "
            "clearly and get things done."
        )
    return MSG_RAYA_NEUTRAL
