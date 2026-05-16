# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Aggregate bounded text from a file or directory for ``privacy scan`` (CLI / tooling)."""

from __future__ import annotations

from pathlib import Path

_TEXT_SUFFIXES = frozenset(
    {
        ".md",
        ".txt",
        ".py",
        ".toml",
        ".json",
        ".yaml",
        ".yml",
        ".rst",
        ".env.example",
    }
)


def aggregate_text_for_scan(
    root: Path,
    *,
    max_files: int = 48,
    max_bytes_per_file: int = 96_000,
    max_total_chars: int = 400_000,
) -> str:
    root = root.expanduser().resolve()
    parts: list[str] = []
    total = 0
    if root.is_file():
        low = root.name.lower()
        if low == ".env" or low.startswith(".env.") or low.endswith(".pem") or low.endswith(".key"):
            return ""
        raw = root.read_text(encoding="utf-8", errors="replace")
        return raw[:max_total_chars]
    if not root.is_dir():
        return ""
    n_files = 0
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        low = p.name.lower()
        if low == ".env" or low.startswith(".env.") or low.endswith(".pem") or low.endswith(".key"):
            continue
        if p.suffix.lower() not in _TEXT_SUFFIXES and p.name != ".env.example":
            continue
        if "node_modules" in p.parts or ".git" in p.parts or ".venv" in p.parts:
            continue
        try:
            chunk = p.read_text(encoding="utf-8", errors="replace")[:max_bytes_per_file]
        except OSError:
            continue
        header = f"\n\n===== {p.relative_to(root)} =====\n"
        piece = header + chunk
        if total + len(piece) > max_total_chars:
            piece = piece[: max_total_chars - total]
        parts.append(piece)
        total += len(piece)
        n_files += 1
        if n_files >= max_files or total >= max_total_chars:
            break
    return "".join(parts)
