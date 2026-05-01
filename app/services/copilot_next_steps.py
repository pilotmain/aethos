"""Heuristics for when to show co-pilot 'Next steps' (chat-only; no new UI)."""

from __future__ import annotations

import re


def is_trivial_user_message(text: str) -> bool:
    """Short acknowledgements / greetings — no 'Next steps' block."""
    t = (text or "").strip()
    if len(t) < 2:
        return True
    low = t.lower()
    trivial_one_word = {
        "ok",
        "k",
        "thanks",
        "thx",
        "ty",
        "yes",
        "no",
        "cool",
        "nice",
        "yep",
        "nope",
        "hi",
        "hey",
        "hello",
        "bye",
    }
    if low in trivial_one_word and len(t) <= 12:
        return True
    if len(t) <= 10 and re.match(r"^(thanks|thx|ty|ok|k|yep|sure|got it|sounds good)[.!\s]*$", low):
        return True
    if len(t.split()) <= 2 and low in ("thank you", "sounds good", "got it"):
        return True
    return False


def is_goal_oriented_user_message(text: str) -> bool:
    """
    Heuristic: user is driving toward an outcome (not a pure definition question).
    Used in tests and optional gating; the model also decides next_steps.
    """
    raw = (text or "").strip()
    if len(raw.split()) < 3:
        return False
    t = raw.lower()
    if re.search(
        r"\b(launch|ship|go to market|gtm|market|positioning|website|landing|"
        r"grow|scale|revenue|customers|competitor|roadmap|strategy|messaging|brand|analyze|analyse|"
        r"product|business|founder|saas|campaign)\b",
        t,
    ):
        return True
    if re.search(
        r"\b(i want to|help me|need to|trying to|going to|we should|"
        r"let'?s|create a|build a|improve my|improve the)\b",
        t,
    ):
        return True
    if re.search(r"@marketing|@strategy|@dev|/doc\b|@research", t):
        return True
    return False


def format_next_steps_block(items: list[str]) -> str:
    lines = [f"- {x.strip()}" for x in items if (x or "").strip()]
    if not lines:
        return ""
    return "Next steps:\n" + "\n".join(lines)


def response_includes_next_steps_block(assistant_text: str) -> bool:
    """
    True if the model already added a 'Next steps' block (## heading or app-style label).
    Used to avoid duplicating the co-pilot-appended 'Next steps:\\n- …' list.
    Also treat **## Next step** and **Next step:** (singular) as covered.
    """
    s = assistant_text or ""
    if re.search(r"(?i)(^|\n)##\s*next (?:step|steps)\b", s):
        return True
    if re.search(r"(?i)(^|\n)next (?:step|steps):\s*(\n|$)", s):
        return True
    if re.search(r"(?i)(^|\n)\*?\*?next (?:step|steps)\*?\*?\s*\n", s):
        return True
    return False


def should_append_next_steps(
    behavior: str,
    user_message: str,
    next_steps: list[str] | None,
    *,
    assistant_text: str | None = None,
) -> bool:
    if not next_steps:
        return False
    if behavior not in ("clarify", "assist", "reduce"):
        return False
    if is_trivial_user_message(user_message):
        return False
    if (assistant_text or "").strip() and response_includes_next_steps_block(assistant_text):
        return False
    return True
