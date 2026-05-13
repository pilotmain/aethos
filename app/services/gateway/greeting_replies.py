# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Short deterministic replies for bare greetings (gateway + web via ``handle_full_chat``)."""

from __future__ import annotations

import re


def greeting_reply_for_text(raw: str) -> str:
    t = (raw or "").strip().lower()
    t = re.sub(r"[\s!.?…,:;]+$", "", t).strip()
    if t.startswith("good morning"):
        return (
            "Good morning — I'm AethOS, your agentic operating system.\n\n"
            "How can I help you today?\n\n"
            "Try: *create a marketing agent* or *help* when you want ideas."
        )
    if t.startswith("good afternoon"):
        return (
            "Good afternoon — I'm AethOS, your agentic operating system.\n\n"
            "What would you like to tackle?\n\n"
            "Try: *create a marketing agent* or *help* for a quick tour."
        )
    if t.startswith("good evening"):
        return (
            "Good evening — I'm AethOS, your agentic operating system.\n\n"
            "What can I help with?\n\n"
            "Try: *create a marketing agent* or *help* when you're ready."
        )
    if re.match(r"^hey\b", t):
        return (
            "👋 Hey — I'm AethOS, your agentic operating system.\n\n"
            "What can I do for you?\n\n"
            "Try: *create a marketing agent* or *help*."
        )
    if re.match(r"^hello\b", t):
        return (
            "👋 Hello — I'm AethOS, your agentic operating system.\n\n"
            "How can I help you today?\n\n"
            "Try: *create a marketing agent* or *help*."
        )
    # hi, greetings, sup, howdy, yo, hiya
    return (
        "👋 Hi — I'm AethOS, your agentic operating system.\n\n"
        "How can I help you today?\n\n"
        "Try: *create a marketing agent* or *help*."
    )


__all__ = ["greeting_reply_for_text"]
