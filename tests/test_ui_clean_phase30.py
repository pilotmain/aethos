# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 30 — mission-control and chat web sources must not reintroduce legacy Nexa copy."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

# User-visible legacy product copy (not internal words like "research" in a label).
LITERAL_BLOCK = [
    "Command Center",
    "@ops",
    "@strategy",
    "@research",
    "@reset",
    '"/agents"',
    "'/agents'",
    "`/agents`",
]

# After removing allowed Next job API paths, no bare /jobs string (legacy route).
# `/custom-agents` does not contain the substring "/agents" (checked).
RE_AT_DEV = re.compile(r"@dev\b")

SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs")


def _web_source_files() -> list[Path]:
    out: list[Path] = []
    for p in WEB.rglob("*"):
        if not p.is_file() or "node_modules" in p.parts or ".next" in p.parts:
            continue
        if p.suffix not in SUFFIXES:
            continue
        out.append(p)
    return sorted(out)


def test_suggestions_ts_uses_nexa_next_phrases() -> None:
    text = (ROOT / "web/lib/suggestions.ts").read_text(encoding="utf-8")
    assert "run dev task" in text
    assert "create a plan" in text
    assert "@dev" not in text


def test_web_sources_phase30_string_blocks() -> None:
    problems: list[str] = []
    for path in _web_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        scrub_jobs = text.replace("/web/jobs", "")
        for lit in LITERAL_BLOCK:
            if lit in text:
                problems.append(f"{rel}: contains {lit!r}")
        if RE_AT_DEV.search(text):
            problems.append(f"{rel}: contains legacy @dev mention")
        if "/jobs" in scrub_jobs:
            problems.append(f"{rel}: contains /jobs outside /web/jobs")
    assert not problems, "\n".join(problems)
