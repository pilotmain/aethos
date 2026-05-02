"""Nexa capability registry for mention routing and help copy."""

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
        "display_name": "Development",
        "emoji": "💻",
        "description": "Runs code changes through the local development loop.",
        "capabilities": [
            "code changes",
            "bug fixes",
            "refactors",
            "scheduled tasks",
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
            "task status",
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
    """Short capability lines for help UX (identity-clean; no legacy command hints)."""
    parts: list[str] = []
    for key in _CATALOG_ORDER:
        meta = AGENTS.get(key) or {}
        em = str(meta.get("emoji") or "•")
        name = str(meta.get("display_name") or key)
        desc = str(meta.get("description") or "").strip()
        line = f"{em} **{name}**"
        if desc:
            line += f" — {desc}"
        parts.append(line)
    parts.append("")
    parts.append("(You can also ask Nexa to **create a custom role** with instructions and safety boundaries.)")
    return "\n".join(parts)
