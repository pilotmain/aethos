"""Intent-first reference when users ask what they can do (plain language, no slash roster)."""


def format_command_help_response() -> str:
    return """AethOS — describe what you want

You can use normal language for:

• Multi-step missions and deliverables — say the outcome you want.
• Development work on a connected repo — connect your workspace in Mission Control, then describe the bug or test failure.
• Custom agents — describe the role and what it should do.
• Memory — ask what’s stored or ask to remember something.
• System status — ask how the host is doing.

Paste a public https:// link for read-only summaries when the host allows web access.

You don’t need special syntax — AethOS routes from what you say."""
