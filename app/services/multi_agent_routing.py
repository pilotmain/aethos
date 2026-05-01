"""
Detect multi-agent *capability* questions so they route to agent-team planning, not custom-agent creation.
"""

from __future__ import annotations

import re

_MULTI_SIGNALS: tuple[str, ...] = (
    "multi-agent",
    "multi agent",
    "multiple agents",
    "work autonomously",
    "agents communicate",
    "communicate each other",
    "communicate with each other",
    "agent team",
    "team of agents",
    "autonomous agents",
    "agents working together",
    "without my involvement",
    "each other autonomously",
)

# User is creating a real team / named agent — not a vague "can you" question.
_RE_EXPLICIT_TEAM_OR_NAMED = re.compile(
    r"(?is)\b("
    r"create\s+(?:an?\s+)?(?:multi-agent\s+|multi\s+agent\s+)?(?:dev\s+)?(?:agent\s+)?team\b|"
    r"(?:called|named)\s+@\s*[\w-]{2,40}\b"
    r")"
)


def reply_multi_agent_capability_clarification() -> str:
    return (
        "Yes — Nexa can support an **agent team** (multiple coordinated agents), but I need a **concrete goal** "
        "before setting anything up.\n\n"
        "Examples:\n"
        "• **create an agent team** — prepare your team workspace\n"
        "• **create a multi-agent dev team for building a dashboard** — ties the team to a goal\n"
        "• **ask my team to …** — queues tracked assignments\n"
        "• Mention roles like **@orchestrator**, **@dev**, **@research**, **@qa** when you assign work\n\n"
        "What should the team work on first?"
    ).strip()


def is_multi_agent_capability_question(text: str) -> bool:
    """
    Broad multi-agent *questions* (not explicit ``create … called @handle`` or team-for goal syntax).
    """
    raw = (text or "").strip()
    if not raw:
        return False
    tl = raw.lower()
    if _RE_EXPLICIT_TEAM_OR_NAMED.search(raw):
        return False
    hits = sum(1 for s in _MULTI_SIGNALS if s in tl)
    if hits == 0:
        return False
    question_like = (
        "?" in raw
        or tl.startswith(("can ", "could ", "how ", "what ", "why ", "would ", "is ", "are "))
        or "can you" in tl
        or "could you" in tl
    )
    if hits >= 2:
        return True
    return hits >= 1 and question_like
