from __future__ import annotations

ALLOWED_COMMANDS = {
    "review-last-change",
    "run-tests",
    "create-cursor-task",
    "prepare-fix",
    "summarize-project",
}

_COMMANDS_REQUIRING_INSTRUCTION = frozenset({"create-cursor-task", "prepare-fix"})


def is_dev_command(text: str) -> bool:
    return text.strip().lower().startswith("/dev")


def parse_local_action(text: str) -> dict[str, str]:
    raw = text.strip()
    low = raw.lower()
    if not low.startswith("/dev"):
        raise ValueError("Not a dev command")

    body = raw[len("/dev") :].lstrip()
    if not body:
        raise ValueError("Missing dev command — try /dev run-tests or /dev create-cursor-task …")

    parts = body.split(maxsplit=1)
    command_type = parts[0].strip().lower()
    instruction = parts[1].strip() if len(parts) > 1 else ""

    if command_type not in ALLOWED_COMMANDS:
        raise ValueError(
            f"Unsupported command: {command_type}. "
            f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    if command_type in _COMMANDS_REQUIRING_INSTRUCTION and not instruction:
        raise ValueError(f"Command /dev {command_type} needs an instruction after the command name.")

    return {
        "command_type": command_type,
        "instruction": instruction,
    }
