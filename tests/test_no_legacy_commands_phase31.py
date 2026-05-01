"""Phase 31 — user-facing copy stays intent-first; block legacy slash/persona hints in scoped paths."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LITERAL_BLOCK = [
    "/jobs",
    "/context",
    "Command Center",
    "@ops",
    "@strategy",
    "@research",
]

RE_AT_DEV = re.compile(r"@dev\b")

WEB_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs")


def _scrub_web_jobs(text: str) -> str:
    """`/web/jobs` contains the substring `/jobs`; allow only that API path."""
    return text.replace("/web/jobs", "")


def test_command_help_py_phase31_clean() -> None:
    p = ROOT / "app/services/command_help.py"
    text = p.read_text(encoding="utf-8")
    rel = p.relative_to(ROOT)
    for lit in LITERAL_BLOCK:
        assert lit not in text, f"{rel}: contains {lit!r}"
    assert not RE_AT_DEV.search(text), f"{rel}: legacy @dev mention"


def test_app_bot_phase31_clean() -> None:
    problems: list[str] = []
    for path in sorted((ROOT / "app/bot").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        for lit in LITERAL_BLOCK:
            if lit in text:
                problems.append(f"{rel}: contains {lit!r}")
        if RE_AT_DEV.search(text):
            problems.append(f"{rel}: contains legacy @dev mention")
    assert not problems, "\n".join(problems)


def test_web_sources_phase31_clean() -> None:
    problems: list[str] = []
    web = ROOT / "web"
    for path in web.rglob("*"):
        if not path.is_file() or "node_modules" in path.parts or ".next" in path.parts:
            continue
        if path.suffix not in WEB_SUFFIXES:
            continue
        text = _scrub_web_jobs(path.read_text(encoding="utf-8", errors="replace"))
        rel = path.relative_to(ROOT)
        for lit in LITERAL_BLOCK:
            if lit in text:
                problems.append(f"{rel}: contains {lit!r}")
        if RE_AT_DEV.search(text):
            problems.append(f"{rel}: contains legacy @dev mention")
        if "/jobs" in text:
            problems.append(f"{rel}: contains /jobs outside /web/jobs")
        if "/context" in text:
            problems.append(f"{rel}: contains /context")
    assert not problems, "\n".join(problems)
