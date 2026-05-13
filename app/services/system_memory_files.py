# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SECRET_PATTERNS = [
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "bearer ",
    "sk-",
]


@dataclass
class SystemMemorySnapshot:
    soul: str
    memory: str


_CREATOR_SECTION = """## Creator

Name: Raya Ameha Meresa

Role: Creator of AethOS.

Search terms:
- Raya
- Raya Meresa
- Raya Ameha Meresa
"""


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def system_memory_dir() -> Path:
    """Directory for repo-local soul.md + memory.md (docs/development after Phase 4)."""
    return project_root() / "docs" / "development"


def soul_path() -> Path:
    return system_memory_dir() / "soul.md"


def memory_path() -> Path:
    return system_memory_dir() / "memory.md"


def default_soul_md() -> str:
    return f"""# AethOS Soul

## Identity

AethOS is an AI execution system for thinking, deciding, and executing work — creating task-focused agents dynamically when needed.

AethOS may route work through handles and missions (e.g. dev, ops, research); those are execution contexts, not separate products.

## Mission

Help the user move from idea to action safely, clearly, and with human approval for risky steps.

{_CREATOR_SECTION}

## Principles

- Be useful before being impressive.
- Ask for approval before risky actions.
- Never expose secrets.
- Prefer clear execution over vague conversation.
- Treat AethOS as an execution system, not a generic chatbot.
"""


def default_memory_md() -> str:
    return """# AethOS Memory

This file stores durable, non-secret memory that helps AethOS operate consistently.

## Rules

- Do not store API keys, passwords, tokens, or secrets.
- Prefer concise facts.
- Prefer decisions that should persist across sessions.
- Keep short-term conversation context out of this file unless it becomes durable.

## Memories

"""


def ensure_soul_creator_section() -> None:
    """If soul.md exists but lacks a Creator section, append it once."""
    p = soul_path()
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8")
    if "## Creator" in text:
        return
    from app.services.soul_manager import snapshot_repo_soul_file

    snapshot_repo_soul_file()
    p.write_text(text.rstrip() + "\n\n" + _CREATOR_SECTION + "\n", encoding="utf-8")


def ensure_system_memory_files() -> None:
    system_memory_dir().mkdir(parents=True, exist_ok=True)
    if not soul_path().exists():
        soul_path().write_text(default_soul_md(), encoding="utf-8")

    if not memory_path().exists():
        memory_path().write_text(default_memory_md(), encoding="utf-8")

    ensure_soul_creator_section()


def looks_secret_like(text: str) -> bool:
    lower = text.lower()
    return any(pattern in lower for pattern in SECRET_PATTERNS)


def read_system_memory_snapshot(max_chars_each: int = 6000) -> SystemMemorySnapshot:
    ensure_system_memory_files()

    soul = soul_path().read_text(encoding="utf-8")
    memory = memory_path().read_text(encoding="utf-8")
    if len(soul) > max_chars_each:
        soul = soul[-max_chars_each:]
    if len(memory) > max_chars_each:
        memory = memory[-max_chars_each:]

    return SystemMemorySnapshot(soul=soul, memory=memory)


def append_memory_entry(entry: str, *, source: str = "user") -> None:
    ensure_system_memory_files()

    if looks_secret_like(entry):
        raise ValueError("Refusing to store secret-like text in memory.md")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    block = f"""

### {timestamp} — {source}

{entry.strip()}
"""

    with memory_path().open("a", encoding="utf-8") as f:
        f.write(block)
