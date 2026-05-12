# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 26 — command hints must not reference legacy Nexa v1 slash strings."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_hints_no_legacy_slash_strings() -> None:
    text = (ROOT / "web/components/aethos/WorkspaceApp.tsx").read_text(encoding="utf-8")
    # Old hint rows used `{ cmd: "/memory", ... }`. `webFetch("…/agents")` for the API is allowed.
    for bad in ('{ cmd: "/agents"', '{ cmd: "/memory"', '"/dev queue"', '"/project default"'):
        assert bad not in text, f"legacy hint row {bad!r} must be removed"
