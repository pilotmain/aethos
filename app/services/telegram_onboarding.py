"""Telegram-first copy for onboarding, help, and weak-input handling — natural language first."""

from __future__ import annotations

import re

from app.services.general_response import should_skip_weak_input_for_substantive_message


def first_time_nexa_start_text() -> str:
    """No BYOK row yet — welcome without command syntax."""
    return (
        "Welcome to AethOS.\n\n"
        "Tell me what you want to get done — I’ll take care of it.\n\n"
        "You can ask me to fix code issues, run development tasks, plan projects, analyze problems, "
        "create agents, or automate workflows. Just describe the goal — no special syntax.\n\n"
        "When you’re ready for full LLM replies on this host, add an API key the way your setup documents "
        "(Mission Control or host configuration)."
    )


def start_message() -> str:
    return start_message_for_role("owner")


def start_message_for_role(role: str) -> str:
    r = (role or "guest").strip() or "guest"
    base = (
        "Welcome to AethOS.\n\n"
        "Tell me what you want to get done — I’ll take care of it.\n\n"
        "You can ask me to fix code issues, run development tasks, plan projects, analyze problems, "
        "create agents, or automate workflows. No commands needed — just describe the goal.\n\n"
    )
    if r == "owner":
        return (
            base
            + "You have **owner** access on this bot.\n\n"
            + "If something needs your repo or Mission Control connected, I’ll tell you.\n\n"
            + "Only people you trust should use this link; others see the guest experience unless you allow them."
        )
    if r == "trusted":
        return (
            base
            + "You have **trusted** access: chat, planning, and read-only checks where enabled. "
            + "Host-side development and operations stay with the owner of this instance.\n\n"
            + "Say what you’re trying to accomplish — I’ll help within what’s enabled for you."
        )
    if r == "blocked":
        return "This account does not have access to this AethOS instance."
    return (
        base
        + "You can chat, describe plans in your own words, and ask questions. "
        + "Automated development and host operations stay **restricted** until the owner adds you to the trusted list.\n\n"
        + "Tell me what you’re trying to do — I’ll help within what’s enabled for you."
    )


def help_message(has_active_plan: bool, focus_task: str | None) -> str:
    if has_active_plan and focus_task:
        return (
            "AethOS — I’m here to help you move forward.\n\n"
            f"A good place to start: {focus_task}\n\n"
            "Describe what you want in plain language — I’ll take it from there."
        )
    return (
        "AethOS — describe what you want in plain language.\n\n"
        "I can help with brain dumps, planning next steps, when you’re stuck, status updates, "
        "development work when your workspace is connected, and structured missions — just say what you need.\n\n"
        "**Team agents (Mission Control):** say e.g. `create two agents qa_agent and marketing_agent`, "
        "or use `/subagent create <name> <domain>` — then `/subagent list`."
    )


def capability_response() -> str:
    from app.services.system_identity.capabilities import narrative_capability_answer

    return narrative_capability_answer()


def clarify_general_response() -> str:
    return "What’s on your mind? A rough list is enough — I’ll help you narrow it down."


def weak_input_response() -> str:
    return "What are you trying to get done? Describe it in a sentence or two."


def onboarding_deterministic_reply(text: str) -> str | None:
    """
    Short, human replies for very common openers (no internal jargon).

    Returns None so callers can fall back to weak_input_response() or the LLM.
    """
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in {"hi", "hey", "hello", "yo", "sup", "hiya"}:
        return "Hey — what are you trying to get done?"
    if t in {"i need help", "help me", "need help"} or (
        t.startswith("i need help") and len(t) < 48
    ):
        return "Got you. What kind of help — coding, planning, or something else?"
    if any(x in t for x in ("test", "tests")) and any(x in t for x in ("fail", "failing", "broken")):
        return (
            "Alright — I’ll help you fix that.\n\n"
            "Share the error or tell me what’s failing, and I’ll walk you through it or run it for you "
            "if your workspace is connected."
        )
    return None


def is_weak_input(text: str) -> bool:
    if should_skip_weak_input_for_substantive_message(text):
        return False
    t = text.strip().lower()
    if not t:
        return True

    weak_exact = {
        "hi",
        "hey",
        "hello",
        "yo",
        "sup",
        "ok",
        "okay",
        "k",
        "kk",
        "hmm",
        "hm",
        "uh",
        "uhh",
        "lol",
        "heh",
        "thanks",
        "thx",
        "ty",
    }
    if t in weak_exact:
        return True

    if t in {".", "..", "...", "?", "!", "?!", "!?", "…"}:
        return True

    if len(t) <= 5 and all(ch in ".!?… \t\n\r" for ch in t):
        return True

    if re.fullmatch(r"[.!?…\s]{1,6}", t):
        return True

    return False
