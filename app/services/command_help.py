"""Nexa-Next intent-first reference for natural-language ‘what can you do’ questions (no slash-first UX)."""


def format_command_help_response() -> str:
    return """Nexa-Next — intent first

Describe what you want in plain language. Useful phrases:

run mission: "…" — multi-step missions (tasks, artifacts)
run dev: "…" — dev runtime on a registered workspace (tests, coding tasks)
create agent: … — describe a custom agent (parsed server-side); saved agents use @your-handle
show memory — what Nexa remembers (web memory APIs)
show system status — host health and channels

Paste a public https:// link for read-only summaries when web access is enabled on the host.

Nexa routes missions, dev runs, memory, and chat — you do not need to memorize slash commands."""
