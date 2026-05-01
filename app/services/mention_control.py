"""Explicit @agent mention parsing (Telegram and routing). Does not run on non-@ messages."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.agent_catalog import format_available_agents_block

MENTION_ALIASES: dict[str, str] = {
    "reset": "reset",
    "focus": "reset",
    "brain": "reset",
    "dev": "dev",
    "developer": "dev",
    "code": "dev",
    "cursor": "dev",
    "aider": "dev",
    "qa": "qa",
    "test": "qa",
    "tester": "qa",
    "ops": "ops",
    "operator": "ops",
    "health": "ops",
    "strategy": "strategy",
    "orchestrator": "strategy",
    "ceo": "strategy",
    "cto": "strategy",
    "product": "strategy",
    "marketing": "marketing",
    "growth": "marketing",
    "brand": "marketing",
    "research": "research",
    "search": "research",
}

# Catalog key → internal key used by handle_agent_mention and routing
CATALOG_KEY_TO_INTERNAL: dict[str, str] = {
    "reset": "nexa",
    "dev": "developer",
    "qa": "qa",
    "ops": "ops",
    "strategy": "strategy",
    "marketing": "marketing",
    "research": "research",
}


@dataclass
class MentionRoute:
    agent_key: str | None
    text: str
    raw_mention: str | None
    is_explicit: bool
    error: str | None = None


def map_catalog_key_to_internal(catalog_key: str) -> str:
    k = (catalog_key or "").lower().strip()
    return CATALOG_KEY_TO_INTERNAL.get(k, k)


def parse_mention(text: str) -> MentionRoute:
    stripped = text.strip()

    if not stripped.startswith("@"):
        return MentionRoute(
            agent_key=None,
            text=text,
            raw_mention=None,
            is_explicit=False,
        )

    parts = stripped.split(maxsplit=1)
    raw = parts[0][1:].lower().strip()
    remaining = parts[1].strip() if len(parts) > 1 else ""

    agent_key = MENTION_ALIASES.get(raw)

    if not agent_key:
        return MentionRoute(
            agent_key=None,
            text=remaining,
            raw_mention=raw,
            is_explicit=True,
            error=f"Unknown agent: @{raw}",
        )

    return MentionRoute(
        agent_key=agent_key,
        text=remaining,
        raw_mention=raw,
        is_explicit=True,
    )


def format_unknown_mention_message(raw_mention: str) -> str:
    """User-facing list when an @ handle is not in the built-in catalog."""
    who = f"@{raw_mention}" if not raw_mention.startswith("@") else raw_mention
    return (
        f"`{who}` isn’t one of Nexa’s **built-in** agents.\n\n"
        "You can **create a custom agent** with that handle (role, instructions, tools when enabled, and "
        "safety boundaries). Say for example:\n"
        "• Create an agent called **@"
        + (raw_mention or "my_role").strip()[:48]
        + "** — …\n\n"
        "Built-in defaults:\n"
        f"{format_available_agents_block()}"
    )
