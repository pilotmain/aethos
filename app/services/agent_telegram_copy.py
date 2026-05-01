"""Nexa-Next strings for Telegram (no legacy slash roster / persona chips)."""


WELCOME_NEXA = (
    "Welcome to **Nexa** — a privacy-first AI dev OS for missions, dev runs, and chat. "
    "Use **@nexa**, **run dev:** for coding tasks on your worker, **run mission:** for structured work, "
    "and **create agent:** for custom agents. See /help for the full command list."
)


def format_agents_list() -> str:
    return (
        "Nexa — agents\n\n"
        "· @nexa — default assistant\n"
        "· Custom agents — `create agent: …` in chat, `/agent` in Telegram, or the web app\n\n"
        "Try: `run dev: fix the failing test` · `run mission: ship the milestone` · `@nexa hello`"
    )


def format_command_center() -> str:
    return (
        "Nexa\n\n"
        "Workflows:\n"
        "· run dev: … — dev runtime (registered workspace)\n"
        "· run mission: … — structured mission\n"
        "· create agent: … — custom agent\n\n"
        "Chat:\n"
        "· @nexa — assistant\n\n"
        "Try:\n"
        "run dev: add a README section\n"
        "run mission: close the release checklist\n"
        "@nexa what should I focus on?"
    )
