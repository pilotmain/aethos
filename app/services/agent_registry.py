"""In-memory agent catalog; rows in `agent_definitions` are synced on startup."""

# Canonical primary assistant handle (Phase 38 — AethOS rebrand).
PRIMARY_AGENT_KEY = "aethos"
LEGACY_PRIMARY_AGENT_KEYS = frozenset({"nexa", "overwhelm_reset"})

AGENT_EMOJIS: dict[str, str] = {
    PRIMARY_AGENT_KEY: "🧠",
    "nexa": "🧠",  # legacy alias for logs/UI
    "developer": "💻",
    "qa": "🧪",
    "marketing": "📣",
    "strategy": "🧭",
    "ceo": "👤",
    "cto": "🏗️",
    "research": "🔎",
    "personal_admin": "📋",
    "ops": "⚙️",
    "general": "✨",
}

# Keys align with vNext `AGENT_TYPES` + `general` for unclassified routing.
DEFAULT_AGENTS: dict[str, dict[str, object]] = {
    PRIMARY_AGENT_KEY: {
        "display_name": "AethOS",
        "description": "Your personal execution system — think clearly and get things done.",
        "allowed_tools": ["memory", "tasks", "telegram"],
    },
    "developer": {
        "display_name": "Development",
        "description": "Runs code changes through AethOS’s autonomous dev loop.",
        "allowed_tools": ["git", "tests", "aider", "safe_file_read"],
    },
    "qa": {
        "display_name": "QA Agent",
        "description": "Creates test plans, reviews failures, and checks regressions.",
        "allowed_tools": ["tests", "git", "safe_file_read"],
    },
    "marketing": {
        "display_name": "Marketing Agent",
        "description": "Helps with positioning, launch copy, and user messaging.",
        "allowed_tools": ["safe_llm", "memory"],
    },
    "strategy": {
        "display_name": "Strategy Agent",
        "description": "Helps with roadmap, pricing, business decisions, and tradeoffs.",
        "allowed_tools": ["safe_llm", "memory"],
    },
    "ceo": {
        "display_name": "Strategy / CEO Agent",
        "description": "Business priorities, tradeoffs, and focus decisions.",
        "allowed_tools": ["safe_llm", "memory"],
    },
    "cto": {
        "display_name": "CTO / Architecture Agent",
        "description": "Architecture, technical risk, scaling, and security questions.",
        "allowed_tools": ["safe_llm", "memory", "safe_file_read"],
    },
    "research": {
        "display_name": "Research Agent",
        "description": "Web research, competitive analysis, and structured summaries (safe sources only, gated).",
        "allowed_tools": ["safe_llm", "memory"],
    },
    "personal_admin": {
        "display_name": "Personal Admin Agent",
        "description": "Scheduling, errands, and lightweight life ops (memory-backed).",
        "allowed_tools": ["memory", "tasks", "telegram"],
    },
    "ops": {
        "display_name": "Ops Agent",
        "description": "Host/worker health, runtimes, and operational checks (gated, local-first).",
        "allowed_tools": ["safe_file_read", "git", "memory"],
    },
    "general": {
        "display_name": "General",
        "description": "Falls back to AethOS routing when no prior agent handle matches.",
        "allowed_tools": ["safe_llm", "memory", "tasks", "telegram"],
    },
}

MENTION_ALIASES: dict[str, str] = {
    "dev": "developer",
    "nexa": PRIMARY_AGENT_KEY,
    "reset": PRIMARY_AGENT_KEY,
    "overwhelm": PRIMARY_AGENT_KEY,
    "overwhelm_reset": PRIMARY_AGENT_KEY,
    "mkt": "marketing",
    "strat": "strategy",
    "test": "qa",
    "ops": "ops",
    "admin": "ops",
}


def resolve_mention_key(raw: str) -> str | None:
    k = (raw or "").strip().lstrip("@").lower()
    if not k:
        return None
    if k in MENTION_ALIASES:
        return MENTION_ALIASES[k]
    if k in DEFAULT_AGENTS:
        return k
    return None


def normalize_primary_agent_key(key: str | None) -> str:
    """Map legacy primary handles to :data:`PRIMARY_AGENT_KEY`."""
    k = (key or "").strip().lower()
    if k in LEGACY_PRIMARY_AGENT_KEYS or k == "":
        return PRIMARY_AGENT_KEY
    return k


__all__ = [
    "AGENT_EMOJIS",
    "DEFAULT_AGENTS",
    "LEGACY_PRIMARY_AGENT_KEYS",
    "MENTION_ALIASES",
    "PRIMARY_AGENT_KEY",
    "normalize_primary_agent_key",
    "resolve_mention_key",
]
