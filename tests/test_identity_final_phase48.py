# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 48 — identity lock using ``legacy_identity_violations`` on interaction surfaces.

Uses the same scoped paths as ``test_system_identity_locked`` (web, bot, gateway,
channels, plus ``command_help.py`` and ``agent_telegram_copy.py``). Parser-heavy
modules under ``app/services`` are intentionally omitted — they must embed legacy
syntax for routing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.identity import legacy_identity_violations, scrub_allowed_api_paths

ROOT = Path(__file__).resolve().parents[1]

WEB_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs")


def _iter_phase48_surfaces() -> list[Path]:
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


def _prep_for_scan(rel: Path, text: str) -> str:
    if "web" in rel.parts:
        return scrub_allowed_api_paths(text)
    return text


@pytest.mark.parametrize(
    "path",
    _iter_phase48_surfaces(),
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_phase48_no_legacy_identity_on_locked_surfaces(path: Path) -> None:
    raw = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(ROOT)
    prep = _prep_for_scan(rel, raw)
    hits = legacy_identity_violations(prep)
    assert not hits, f"{rel}: {hits!r}"


def test_legacy_helper_detects_sample_violation() -> None:
    assert legacy_identity_violations("Use Command Center for @dev /improve") != []
