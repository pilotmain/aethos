"""Phase 29 — block legacy Mission Control dashboard copy from reappearing in web sources."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Human-visible labels from the old dashboard; must not appear in mission-control UI sources.
BLOCKED = [
    "Workspace Report",
    "File-backed mission_control.md",
    "CUSTOM AGENTS",
    "AGENT TEAM & ASSIGNMENTS",
    "ATTENTION QUEUE",
    "RISK & TRUST SUMMARY",
    "CHANNEL ACTIVITY",
    "RECOMMENDED NEXT ACTIONS",
]

MC_UI_GLOBS = [
    "web/app/mission-control/**/*.tsx",
    "web/components/mission-control/**/*.tsx",
]


def _iter_mc_files() -> list[Path]:
    out: list[Path] = []
    for pattern in MC_UI_GLOBS:
        out.extend(ROOT.glob(pattern))
    return sorted({p for p in out if p.is_file()})


def test_mission_control_ui_has_no_legacy_block_strings() -> None:
    problems: list[str] = []
    for path in _iter_mc_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for s in BLOCKED:
            if s in text:
                problems.append(f"{rel}: contains {s!r}")
    assert not problems, "\n".join(problems)
