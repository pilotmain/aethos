# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Telegram /memory commands for repo-root soul.md and memory.md."""

from __future__ import annotations

import re

from app.services.memory_preferences import (
    count_non_empty_preferences,
    extract_memory_preferences,
)
from app.services.system_memory_files import (
    append_memory_entry,
    ensure_system_memory_files,
    memory_path,
    read_system_memory_snapshot,
    soul_path,
)


def normalize_memory_command_text(text: str) -> str:
    t = (text or "").strip()
    return re.sub(r"^/memory@\S+\b", "/memory", t, flags=re.IGNORECASE)


def format_memory_help() -> str:
    return """Nexa memory files (repo paths: `docs/development/soul.md`, `docs/development/memory.md`):

soul.md — identity, mission, creator, principles
memory.md — durable operating memory

Commands:
/memory
/memory status
/memory soul
/memory search <keyword>
/memory add <text>
/memory reload
"""


def _last_memory_entry_preview(memory_text: str, max_len: int = 450) -> str:
    text = (memory_text or "").strip()
    if not text or "## Memories" not in text:
        tail = text[-max_len:] if len(text) > max_len else text
        return tail or "(none yet)"
    # Timestamped blocks use "### YYYY-MM-DD..."
    chunks = re.split(r"\n(?=### )", text)
    if len(chunks) < 2:
        return "(none yet)"
    last = chunks[-1].strip()
    if len(last) > max_len:
        last = last[:max_len] + "…"
    return last


def format_memory_status() -> str:
    ensure_system_memory_files()
    soul_ok = soul_path().is_file()
    mem_ok = memory_path().is_file()
    snap = read_system_memory_snapshot(max_chars_each=100_000)
    prefs = extract_memory_preferences(snap.memory, snap.soul)
    n = count_non_empty_preferences(prefs)
    soul_txt = soul_path().read_text(encoding="utf-8") if soul_ok else ""
    creator_ok = "## Creator" in soul_txt and "Raya Ameha Meresa" in soul_txt
    last = _last_memory_entry_preview(snap.memory)
    lines = [
        "Nexa memory status:",
        "",
        f"• soul.md: {'found' if soul_ok else 'missing'}",
        f"• memory.md: {'found' if mem_ok else 'missing'}",
        f"• creator: {'configured' if creator_ok else 'not found'}",
        f"• durable preferences detected: {n}",
        "• last memory entry:",
        last,
    ]
    return "\n".join(lines)[:8000]


def handle_memory_search(text: str, *, max_lines: int = 25, max_chars: int = 3500) -> str:
    norm = normalize_memory_command_text(text)
    low = norm.lower()
    if not low.startswith("/memory search"):
        return format_memory_help()
    q = norm[len("/memory search") :].strip().lower()
    if not q:
        return "Usage: /memory search <keyword>"

    ensure_system_memory_files()
    soul_lines = soul_path().read_text(encoding="utf-8").splitlines()
    mem_lines = memory_path().read_text(encoding="utf-8").splitlines()
    hits: list[str] = []
    for label, lines in (("soul.md", soul_lines), ("memory.md", mem_lines)):
        for i, line in enumerate(lines, start=1):
            if q in line.lower():
                hits.append(f"{label}:{i}: {line.strip()[:500]}")
                if len(hits) >= max_lines:
                    break
        if len(hits) >= max_lines:
            break

    if not hits:
        return f"No matches for {q!r} in soul.md or memory.md."

    body = "\n".join(hits)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n…"
    return f"Matches for {q!r}:\n\n{body}"


def format_soul_preview(max_chars: int = 2500) -> str:
    ensure_system_memory_files()
    text = soul_path().read_text(encoding="utf-8")

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n…"

    return f"soul.md:\n\n{text}"


def handle_memory_add(text: str) -> str:
    norm = normalize_memory_command_text(text)
    prefix = "/memory add"
    if not norm.lower().startswith(prefix):
        return format_memory_help()
    entry = norm[len(prefix) :].strip()

    if not entry:
        return "Tell me what to add, like:\n/memory add User prefers concise answers."

    try:
        append_memory_entry(entry, source="telegram")
    except ValueError:
        return "I won’t store that because it looks like it may contain a secret."

    return "Added to memory.md."


def handle_memory_command(text: str) -> str:
    norm = normalize_memory_command_text(text)
    lower = norm.lower().strip()

    if lower == "/memory":
        return format_memory_help()

    if lower == "/memory soul":
        return format_soul_preview()

    if lower.startswith("/memory search"):
        return handle_memory_search(norm)

    if lower == "/memory status":
        return format_memory_status()

    if lower.startswith("/memory add"):
        return handle_memory_add(norm)

    if lower == "/memory reload":
        return "Memory files are read live, so no reload is needed."

    return format_memory_help()
