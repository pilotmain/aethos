# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 33 — identity strings frozen on user-facing and gateway surfaces.

Full-repo purge of legacy persona hints lives in routing modules; this guard locks
the interaction shell (web, bot, gateway funnel, channel adapters, help copy).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LITERAL_BLOCK = [
    "Command Center",
    "/commands",
    "@ops",
    "@strategy",
    "@research",
]
RE_AT_DEV = re.compile(r"@dev\b")
WEB_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs")


def _scrub_web_jobs(text: str) -> str:
    return text.replace("/web/jobs", "")


def _scan_text(rel: Path, text: str, problems: list[str]) -> None:
    for lit in LITERAL_BLOCK:
        if lit in text:
            problems.append(f"{rel}: {lit!r}")
    if "/jobs" in text:
        problems.append(f"{rel}: '/jobs'")
    if "/context" in text:
        problems.append(f"{rel}: '/context'")
    if RE_AT_DEV.search(text):
        problems.append(f"{rel}: legacy @dev mention")


def _iter_locked_sources() -> list[Path]:
    out: list[Path] = []
    for sub in (
        ROOT / "web",
        ROOT / "app" / "bot",
        ROOT / "app" / "services" / "gateway",
        ROOT / "app" / "services" / "channels",
    ):
        if sub.is_dir():
            for p in sub.rglob("*"):
                if not p.is_file():
                    continue
                if "node_modules" in p.parts or ".next" in p.parts:
                    continue
                if sub.name == "web" and p.suffix not in WEB_SUFFIXES:
                    continue
                if sub.name != "web" and p.suffix != ".py":
                    continue
                out.append(p)
    for fp in (
        ROOT / "app" / "services" / "command_help.py",
        ROOT / "app" / "services" / "agent_telegram_copy.py",
    ):
        if fp.is_file():
            out.append(fp)
    return sorted(set(out))


def test_system_identity_locked_surfaces() -> None:
    problems: list[str] = []
    for path in _iter_locked_sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        if "web" in path.parts:
            text = _scrub_web_jobs(text)
        rel = path.relative_to(ROOT)
        _scan_text(rel, text, problems)
    assert not problems, "\n".join(problems)
