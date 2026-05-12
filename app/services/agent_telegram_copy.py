# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""AethOS strings for Telegram (natural language; no legacy slash roster)."""


WELCOME_NEXA = (
    "Welcome to **AethOS** — a privacy-first AI assistant for missions, development, and chat. "
    "Describe what you want in plain language: fixes, plans, research, or automation."
)


def format_agents_list() -> str:
    return (
        "AethOS — agents\n\n"
        "· Default assistant — just talk in this chat\n"
        "· Custom agents — describe one in words, or manage them in the web app\n\n"
        "Examples: “fix the failing test”, “plan the release”, “what should I focus on?”"
    )


def format_command_center() -> str:
    return (
        "AethOS\n\n"
        "You can:\n"
        "· Work on a connected repository (Mission Control + your workspace)\n"
        "· Run structured missions when you describe the outcome\n"
        "· Create or use agents by describing what you need\n\n"
        "Chat naturally — no command memorization required."
    )
