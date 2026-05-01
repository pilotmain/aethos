"""
Lightweight heuristics for human conversation (greetings, capability) without forcing planning.
"""

from __future__ import annotations

import random
import re

BASIC_GREETING_PATTERNS: frozenset[str] = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "yo",
        "sup",
        "hola",
    }
)

_GOOD_TIME = frozenset(
    {
        "good morning",
        "good afternoon",
        "good evening",
    }
)


def detect_greeting_type(text: str) -> str:
    t = (text or "").strip().lower()

    if "good morning" in t:
        return "morning"
    if "good afternoon" in t:
        return "afternoon"
    if "good evening" in t:
        return "evening"
    if t.startswith("hi"):
        return "hi"
    if t.startswith("hey"):
        return "hey"
    if t.startswith("hello"):
        return "hello"
    return "default"


GREETING_REPLIES: dict[str, list[str]] = {
    "morning": [
        "Good morning — I’m here.",
        "Morning — ready when you are.",
        "Good morning. What are we moving forward today?",
    ],
    "afternoon": [
        "Good afternoon — I’m here.",
        "Afternoon. What do you want to work on?",
        "Good afternoon. I’m ready.",
    ],
    "evening": [
        "Good evening — I’m here.",
        "Evening. What do you want to handle?",
        "Good evening. I’m ready when you are.",
    ],
    "hi": [
        "Hi — I’m here.",
        "Hey, I’m here.",
        "Hi. What do you want to work on?",
    ],
    "hey": [
        "Hey — I’m here.",
        "Hey. What are we working on?",
        "Hey, ready when you are.",
    ],
    "hello": [
        "Hello — I’m here.",
        "Hello. What do you want to do?",
        "Hello — ready when you are.",
    ],
    "default": [
        "I’m here.",
        "Ready when you are.",
        "What do you want to work on?",
    ],
}


def is_simple_greeting(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t or len(t) > 200:
        return False
    if t in BASIC_GREETING_PATTERNS:
        return True
    if t in _GOOD_TIME:
        return True
    if t.startswith(("hello ", "hi ", "hey ")) and len(t) < 120:
        return True
    # "Hello, can you say hello back" / short pleasantries
    if re.match(r"^(hi|hello|hey)[,!\s]+", t) and len(t) < 160:
        if any(
            x in t
            for x in (
                "say hello",
                "hello back",
                "say hi",
                "can you",
                "good to",
            )
        ):
            return True
    return False


def simple_greeting_reply(text: str = "") -> str:
    greeting_type = detect_greeting_type(text)
    reply = random.choice(
        GREETING_REPLIES.get(greeting_type, GREETING_REPLIES["default"])
    )
    return (
        f"{reply}\n\n"
        "You can talk normally, or use agents like @dev, @ops, @strategy, @qa, @marketing, @research, or @reset."
    )


def is_basic_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t or len(t) < 4:
        return False
    starters = (
        "what is",
        "what are",
        "who is",
        "how do",
        "how can",
        "how does",
        "why ",
        "why?",
        "can you",
        "could you",
        "tell me",
        "explain",
        "where is",
        "when ",
    )
    return t.startswith(starters) or t.endswith("?") and len(t) > 12


def is_casual_capability_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t or len(t) > 220:
        return False
    if "random" in t and "question" in t:
        return True
    if re.search(
        r"\b(can|could)\s+you\s+help\s+(with|me)\b",
        t,
    ) and "agent" not in t:
        if "command" in t or "code" in t or "dev" in t or "ops" in t:
            return False
        return True
    return False


def casual_capability_reply() -> str:
    return (
        "Yes. I can answer normal questions, help you think through ideas, and run execution work when you want action.\n\n"
        "Strong areas include:\n"
        "• daily planning and overwhelm (Reset)\n"
        "• development tasks on your codebase (jobs/missions, approval-gated)\n"
        "• ops, status, and host checks\n"
        "• product strategy and planning\n\n"
        "I create task-focused agents dynamically when the work needs them.\n\n"
        "What would you like to do?"
    )


def fallback_general_reply(text: str) -> str:
    _ = text
    return (
        "I can help with that at a basic level.\n\n"
        "If it needs action, I’ll run or queue execution (approval-gated when needed). "
        "If it is just a question, I’ll answer directly."
    )


def should_skip_weak_input_for_substantive_message(text: str) -> bool:
    """Do not use weak-onboarding when the user sent a real question or sentence."""
    from app.services.intent_classifier import is_command_question

    t = (text or "").strip()
    if is_simple_greeting(t):
        return True
    if is_basic_question(t):
        return True
    if is_command_question(t) or is_command_question_style(t):
        return True
    if len(t) > 20 and "?" in t:
        return True
    if len(t) > 40 and t.lower() not in BASIC_GREETING_PATTERNS:
        return True
    return False


def is_command_question_style(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    pats = (
        "what commands",
        "what can you do",
        "list commands",
        "available commands",
        "/help",
    )
    return any(p in t for p in pats)


def strip_correction_prefix(text: str) -> str:
    prefixes = [
        "no i asked about",
        "no, i asked about",
        "i asked about",
        "that's not what i asked",
        "thats not what i asked",
    ]
    t = (text or "").strip()
    low = t.lower()
    for p in prefixes:
        if low.startswith(p):
            return t[len(p) :].strip(" .,:-")
    return t


def looks_like_general_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if "?" in t:
        return True
    starters = (
        "what ",
        "why ",
        "how ",
        "when ",
        "where ",
        "who ",
        "explain ",
        "compare ",
        "summarize ",
        "summarise ",
        "tell me about ",
        "give me an update",
        "give me update",
        "can you explain",
        "can you compare",
    )
    return t.startswith(starters)
