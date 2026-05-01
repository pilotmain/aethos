"""Nexa-Next command and workflow reference for natural-language 'what can you do' style questions."""


def format_command_help_response() -> str:
    return """Nexa — commands & workflows

Chat:
— @nexa — default assistant (plain chat works too)
— create agent: … — describe a custom agent (parsed server-side); saved agents are @your-handle

Structured work:
— run mission: … — multi-step missions (tasks, artifacts)
— run dev: … — dev runtime on a registered workspace (tests, coding tasks)
— schedule task … — recurring work when scheduling is enabled

Memory & status:
— show memory — what Nexa remembers (web memory APIs on nexa-next)
— show system status — host health and channels

URLs:
Paste a public https:// link for read-only summaries when web access is enabled on the host.

You can also speak naturally — Nexa routes into missions, dev runs, or chat."""
