"""In-memory agent catalog; rows in `agent_definitions` are synced on startup."""

AGENT_EMOJIS: dict[str, str] = {
    "nexa": "🧠",
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
    "nexa": {
        "display_name": "Nexa",
        "description": "Your personal execution system — think clearly and get things done.",
        "allowed_tools": ["memory", "tasks", "telegram"],
    },
    "developer": {
        "display_name": "Developer Agent",
        "description": "Handles code changes through the autonomous dev loop (Dev Agent).",
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
        "description": "Falls back to Nexa routing (command center) when no specialist matches.",
        "allowed_tools": ["safe_llm", "memory", "tasks", "telegram"],
    },
}

MENTION_ALIASES: dict[str, str] = {
    "dev": "developer",
    "reset": "nexa",
    "overwhelm": "nexa",
    "overwhelm_reset": "nexa",
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
