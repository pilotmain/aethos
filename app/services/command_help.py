"""Nexa command and mention reference for natural-language 'what can you do' style questions."""


def format_command_help_response() -> str:
    return """Nexa Command Center

Core commands:
— /agents → list all agents
— /agents status → system status
— /jobs → list jobs
— /job <id> → job details
— /dev health → dev worker status
— /context → show current context

Agent commands:
— @dev <task> → create dev job
— @ops health → system health
— @ops logs → logs
— @strategy <question> → planning help
— @marketing <task> → messaging (with a public URL, uses read-only page fetch; add “web search” for supplemental search when enabled on the host)
— @marketing analyze pilotmain.com
— @marketing web search on pilotmain.com and suggest positioning
— @marketing analyze https://example.com
— @marketing web search on example.com and suggest positioning
— @marketing summarize products on https://example.com
— @research <topic> → research
— @research check https://example.com — read a public page (read-only)
— @research summarize https://example.com — same; Nexa fetches visible text
— @research search the web for <topic> — web search (optional; needs `NEXA_WEB_SEARCH_ENABLED` + provider key on the host)
— @research compare OpenClaw and OpenCode — web search when enabled, or a structured answer otherwise
— @reset <thoughts> → organize thinking

Public URLs: when web access is enabled on the host, you can also ask in normal chat
“check https://example.com” or “what’s on this site?” with a link — Nexa uses a server-side public fetch (no logins, Phase 1).

Web search: optional. When it is not enabled, Nexa can still read direct public links you paste. The host sets `NEXA_WEB_SEARCH_ENABLED=true` and a provider key (see doctor / `.env.example`).

Examples:
@dev add README note
@ops health
@research check https://example.com
@research search the web for recent AI coding tools
@strategy what should we build next?

You can also just talk — Nexa will route automatically."""
