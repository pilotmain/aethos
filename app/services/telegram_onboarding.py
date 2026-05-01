"""Telegram-first copy for onboarding, help, and weak-input handling."""

from __future__ import annotations

import re

from app.services.general_response import should_skip_weak_input_for_substantive_message


def first_time_nexa_start_text() -> str:
    """No BYOK row in the DB yet — short default onboarding for all roles (until someone stores a key)."""
    return (
        "Welcome to **Nexa**.\n\n"
        "Setup takes about 30 seconds:\n"
        "1. Add an API key:\n"
        "   `/key set openai sk-…`  or  `/key set anthropic sk-ant-…`\n"
        "2. Ask anything.\n\n"
        "No dev install required on your side. A key is for the LLM only, not for Dev or Ops. Use /access to see your role."
    )


def start_message() -> str:
    return start_message_for_role("owner")


def start_message_for_role(role: str) -> str:
    r = (role or "guest").strip() or "guest"
    if r == "owner":
        return (
            "Welcome to **Nexa** Command Center.\n\n"
            "You have **owner** access on this bot.\n\n"
            "Try:\n"
            "• /dev doctor — local health, DB, and access summary\n"
            "• /agents\n"
            "• @dev — queue work on the host dev agent (when the worker is set up)\n"
            "• /help for the full list\n\n"
            "Nexa still needs your project paths and local worker on the machine you control; "
            "strangers on this link only get the guest view unless you add their Telegram id in env."
        )
    if r == "trusted":
        return (
            "Welcome to **Nexa**.\n\n"
            "You have **trusted** access: chat, planning, and some read-only stack checks."
            " Dev and Ops execution on the host is reserved for the owner of this instance.\n\n"
            "Try @reset, /command, or /access to see your capabilities, and /help for commands."
        )
    if r == "blocked":
        return "This account does not have access to this Nexa instance."
    return (
        "Welcome to **Nexa**.\n\n"
        "You can:\n"
        "• ask questions and use normal chat\n"
        "• organize and plan with @reset\n"
        "• see high-level help with /agents, /command, and /access\n"
        "• add your own **OpenAI** or **Anthropic** key for chat: `/key set …` (if the host enabled encrypted storage; see /help and README)\n"
        "• /help for commands\n\n"
        "Dev Agent and host-side Ops on this instance are **restricted** until the owner "
        "adds you to the trusted list. Use /access to see what is enabled for you."
    )


def help_message(has_active_plan: bool, focus_task: str | None) -> str:
    if has_active_plan and focus_task:
        return (
            "Nexa — I can help you move forward.\n\n"
            f"Where to start: {focus_task}\n\n"
            "Or send a fresh brain dump whenever, or /agents to see your agents."
        )
    return (
        "You can use Nexa in three simple ways:\n\n"
        "1. Dump everything on your mind — I’ll simplify it to next steps\n"
        "2. Say you're stuck — a small nudge to move\n"
        "3. Status updates and “not done” — to keep the loop going\n\n"
        "Type /help for the full command list, or /agents to see the agent roster."
    )


def capability_response() -> str:
    return (
        "Nexa is a **multi-agent system**: built-in specialists (Developer, QA, Ops, Strategy, Marketing, Research) "
        "plus **custom agents** you define — roles, instructions, governance boundaries. Dev and Ops execute on your "
        "machine through jobs when approved; custom agents stay inside Nexa’s permission and audit layer."
    )


def clarify_general_response() -> str:
    return "What’s going on in your head right now? A rough list is enough — I’ll help you make it smaller."


def weak_input_response() -> str:
    return (
        "Send me everything that's on your mind right now.\n\n"
        "I'll turn it into a simple plan."
    )


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

    if len(t) <= 5 and all(ch in ".!?…\s" for ch in t):
        return True

    if re.fullmatch(r"[.!?…\s]{1,6}", t):
        return True

    return False
