"""Nexa agent registry for command-center UX and mention help."""

AGENTS: dict[str, dict[str, object]] = {
    "reset": {
        "display_name": "Reset Agent",
        "emoji": "🧠",
        "description": "Turns mental chaos into calm next steps.",
        "capabilities": [
            "brain dumps",
            "prioritization",
            "stuck loops",
            "daily focus",
        ],
    },
    "dev": {
        "display_name": "Dev Agent",
        "emoji": "💻",
        "description": "Works on code through the local autonomous dev loop.",
        "capabilities": [
            "code changes",
            "bug fixes",
            "refactors",
            "worker jobs",
            "test runs",
        ],
    },
    "qa": {
        "display_name": "QA Agent",
        "emoji": "🧪",
        "description": "Reviews tests, failures, and regressions.",
        "capabilities": [
            "test review",
            "failure analysis",
            "regression planning",
            "acceptance checks",
        ],
    },
    "ops": {
        "display_name": "Ops Agent",
        "emoji": "⚙️",
        "description": "Checks system health, worker status, and execution state.",
        "capabilities": [
            "worker heartbeat",
            "job queue",
            "runtime health",
            "logs",
        ],
    },
    "strategy": {
        "display_name": "Strategy Agent",
        "emoji": "🧭",
        "description": "Helps with product direction, roadmap, tradeoffs, and decisions.",
        "capabilities": [
            "roadmap",
            "positioning",
            "tradeoffs",
            "business model",
        ],
    },
    "marketing": {
        "display_name": "Marketing Agent",
        "emoji": "📣",
        "description": "Helps with messaging, launches, positioning, and content.",
        "capabilities": [
            "landing copy",
            "launch posts",
            "positioning",
            "user personas",
        ],
    },
    "research": {
        "display_name": "Research Agent",
        "emoji": "🔎",
        "description": "Finds, compares, and summarizes information.",
        "capabilities": [
            "research",
            "comparison",
            "summaries",
            "source-backed findings",
        ],
    },
}

_CATALOG_ORDER: tuple[str, ...] = (
    "reset",
    "dev",
    "qa",
    "ops",
    "strategy",
    "marketing",
    "research",
)


def format_available_agents_block() -> str:
    """Lines like \"🧠 @reset\" for error UX."""
    parts: list[str] = []
    for key in _CATALOG_ORDER:
        meta = AGENTS.get(key) or {}
        em = str(meta.get("emoji") or "•")
        parts.append(f"{em} @{key}")
    parts.append("")
    parts.append("(You can also **create custom agents** with your own @handle.)")
    return "\n".join(parts)
